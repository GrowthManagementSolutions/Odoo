from odoo import SUPERUSER_ID, api

# (rule xmlid, route xmlid, product xmlid) for the seeded rules, so an
# unregistered row can be adopted under the id the data file expects.
SEEDED_RULES = [
    ('rule_broadvoice_sandler_ucaas', 'route_broadvoice_sandler',
     'product_telecommunications_ucaas'),
    ('rule_broadvoice_telarus_ucaas', 'route_broadvoice_telarus',
     'product_telecommunications_ucaas'),
    ('rule_zoom_telarus_ucaas', 'route_zoom_telarus',
     'product_telecommunications_ucaas'),
    ('rule_zoom_sandler_ucaas', 'route_zoom_sandler',
     'product_telecommunications_ucaas'),
    ('rule_square_direct_pos', 'route_square_direct',
     'product_point_of_sale_full_point_of_sale_systems'),
    ('rule_square_direct_payment_processing', 'route_square_direct',
     'product_payment_processing_solutions_payment_processing'),
    ('rule_cci_direct_ucaas', 'route_cci_direct',
     'product_telecommunications_ucaas'),
    ('rule_cci_direct_best_effort_internet', 'route_cci_direct',
     'product_internet_service_best_effort_internet'),
    ('rule_cci_direct_ethernet_fiber_metro_e', 'route_cci_direct',
     'product_internet_service_ethernet_fiber_metro_e'),
]


def _has_column(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def _has_table(cr, table):
    cr.execute("""
        SELECT 1 FROM information_schema.tables WHERE table_name = %s
    """, (table,))
    return bool(cr.fetchone())


def _log(env, cr, message):
    env['ir.logging'].sudo().create({
        'name': 'crm_deals.migration', 'type': 'server', 'level': 'INFO',
        'dbname': cr.dbname, 'message': message,
        'path': 'migrations/19.0.1.0.18/pre-migration.py',
        'func': 'migrate', 'line': '0',
    })


def migrate(cr, version):
    """Prepare product.route.rule for its restructured shape.

    Each step is skipped when its data is absent, so this runs cleanly whether
    the database holds the shape #53 actually shipped (``recurring_basis``, no
    ``spiff_type``, no tier model) or the variant with ``basis`` /
    ``spiff_type`` / ``product.route.spiff.tier``.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    notes = []

    # --- 1. basis -> recurring_basis -----------------------------------
    if _has_column(cr, 'product_route_rule', 'basis'):
        if not _has_column(cr, 'product_route_rule', 'recurring_basis'):
            cr.execute("ALTER TABLE product_route_rule "
                       "RENAME COLUMN basis TO recurring_basis")
            notes.append('renamed basis to recurring_basis')
        # An NRC-only rule keeps its margin and loses its recurring part.
        if _has_column(cr, 'product_route_rule', 'nrc_margin_type'):
            cr.execute("""
                UPDATE product_route_rule
                   SET recurring_basis = 'none'
                 WHERE recurring_basis = 'nrc'
            """)
            notes.append('%s nrc-basis rule(s) moved to recurring_basis none'
                         % cr.rowcount)

    # --- 2. spiff_type and the tier table ------------------------------
    if _has_column(cr, 'product_route_rule', 'spiff_type') \
            and _has_table(cr, 'product_route_spiff_tier'):
        # A flat rule already carries its multiplier; a tiered one takes the
        # lowest tier, with a single higher tier becoming the step-up.
        cr.execute("""
            SELECT r.id, count(t.id)
              FROM product_route_rule r
              JOIN product_route_spiff_tier t ON t.rule_id = r.id
             WHERE r.spiff_type = 'tiered'
          GROUP BY r.id
        """)
        for rule_id, tier_count in cr.fetchall():
            cr.execute("""
                SELECT min_qty, multiplier FROM product_route_spiff_tier
                 WHERE rule_id = %s ORDER BY min_qty, id
            """, (rule_id,))
            tiers = cr.fetchall()
            cr.execute("""
                UPDATE product_route_rule SET spiff_multiplier = %s
                 WHERE id = %s
            """, (tiers[0][1], rule_id))
            if tier_count == 2:
                cr.execute("""
                    UPDATE product_route_rule
                       SET spiff_step_qty = %s, spiff_step_multiplier = %s
                     WHERE id = %s
                """, (tiers[1][0], tiers[1][1], rule_id))
            elif tier_count > 2:
                notes.append(
                    'rule id=%s had %s SPIFF tiers - only the lowest was kept, '
                    'review it by hand' % (rule_id, tier_count))
        cr.execute("DROP TABLE IF EXISTS product_route_spiff_tier")
        notes.append('dropped product_route_spiff_tier')

    # --- 3. nrc_margin_type becomes required with a 'none' default ------
    if _has_column(cr, 'product_route_rule', 'nrc_margin_type'):
        cr.execute("""
            UPDATE product_route_rule SET nrc_margin_type = 'none'
             WHERE nrc_margin_type IS NULL
        """)
        if cr.rowcount:
            notes.append('%s rule(s) given nrc_margin_type none' % cr.rowcount)

    # --- 4. drop the view that still references offering_ids ------------
    # views/product_views.xml holds two views on product.template. Writing
    # either one revalidates the whole inheritance tree, which still contains
    # the stored "Suppliers & Routes" arch referencing the removed
    # offering_ids. Deleting it here lets the data file recreate it from the
    # new arch; nothing else refers to it.
    cr.execute("""
        DELETE FROM ir_ui_view
         WHERE id IN (
            SELECT res_id FROM ir_model_data
             WHERE module = 'crm_deals' AND model = 'ir.ui.view'
               AND name = 'product_template_form_suppliers_routes')
    """)
    if cr.rowcount:
        cr.execute("""
            DELETE FROM ir_model_data
             WHERE module = 'crm_deals' AND model = 'ir.ui.view'
               AND name = 'product_template_form_suppliers_routes'
        """)
        notes.append('dropped the stale Suppliers & Routes view arch')

    # --- 5. adopt unregistered seeded rules ----------------------------
    # #53's data file was loaded by an upgrade that later rolled back, leaving
    # some rules in place without an ir.model.data row. Registering them under
    # the ids the data file uses means the noupdate records match them instead
    # of creating duplicates that would breach the overlap constraint.
    # Resolved with SQL, not env.ref: during a pre-migration the new models
    # are not in the registry yet, so env.ref on one raises KeyError.
    def res_id(xmlid):
        cr.execute("""
            SELECT res_id FROM ir_model_data
             WHERE module = 'crm_deals' AND name = %s
        """, (xmlid,))
        row = cr.fetchone()
        return row[0] if row else None

    adopted = 0
    for rule_xmlid, route_xmlid, product_xmlid in SEEDED_RULES:
        if res_id(rule_xmlid):
            continue
        route_id, product_id = res_id(route_xmlid), res_id(product_xmlid)
        if not route_id or not product_id:
            continue
        cr.execute("""
            SELECT r.id FROM product_route_rule r
             WHERE r.route_id = %s AND r.product_tmpl_id = %s
               AND NOT EXISTS (
                   SELECT 1 FROM ir_model_data d
                    WHERE d.model = 'product.route.rule' AND d.res_id = r.id)
             ORDER BY r.id LIMIT 1
        """, (route_id, product_id))
        row = cr.fetchone()
        if row:
            cr.execute("""
                INSERT INTO ir_model_data
                    (module, name, model, res_id, noupdate, create_date,
                     write_date)
                VALUES ('crm_deals', %s, 'product.route.rule', %s, true,
                        now(), now())
            """, (rule_xmlid, row[0]))
            adopted += 1
    if adopted:
        notes.append('adopted %s unregistered seeded rule(s)' % adopted)

    if notes:
        _log(env, cr, 'Route rule restructure: ' + '; '.join(notes) + '.')
