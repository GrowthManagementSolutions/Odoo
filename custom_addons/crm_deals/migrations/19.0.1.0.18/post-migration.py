from odoo import SUPERUSER_ID, api


def _has_table(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s",
               (table,))
    return bool(cr.fetchone())


def _has_column(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Carry the offerings' default route onto the rules, then drop offerings.

    Runs post-migrate because ``is_default`` is a new column: it does not
    exist yet while the pre-migration runs. The seeded rules already carry the
    flag from the data file, so for those this is a no-op; it exists for
    offerings a user added by hand.

    A product is now sold by a supplier when it has a rule on one of that
    supplier's routes, so the offering model, its table and
    ``res.partner.default_route_id`` all go.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    notes = []

    # Odoo adds a boolean column without a default as NULL, and "NOT NULL" is
    # NULL rather than true, which would silently exclude every pre-existing
    # row from the update below.
    cr.execute("UPDATE product_route_rule SET is_default = false "
               "WHERE is_default IS NULL")

    if _has_table(cr, 'product_supplier_offering') \
            and _has_column(cr, 'product_supplier_offering', 'default_route_id'):
        # The rule for that product on that route, effective today.
        cr.execute("""
            UPDATE product_route_rule r
               SET is_default = true
              FROM product_supplier_offering o
             WHERE o.default_route_id = r.route_id
               AND o.product_tmpl_id = r.product_tmpl_id
               AND r.date_from <= CURRENT_DATE
               AND (r.date_to IS NULL OR r.date_to >= CURRENT_DATE)
               AND r.is_default IS NOT TRUE
        """)
        if cr.rowcount:
            notes.append('%s rule(s) flagged as the default route'
                         % cr.rowcount)
        # Offerings whose default route has no matching effective rule: there
        # is nowhere to carry the flag, so they are reported instead.
        cr.execute("""
            SELECT o.id, p.name, s.name
              FROM product_supplier_offering o
              JOIN product_template t ON t.id = o.product_tmpl_id
              LEFT JOIN res_partner s ON s.id = o.supplier_id
              LEFT JOIN LATERAL (SELECT t.name->>'en_US' AS name) p ON true
             WHERE o.default_route_id IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM product_route_rule r
                    WHERE r.route_id = o.default_route_id
                      AND r.product_tmpl_id = o.product_tmpl_id
                      AND r.date_from <= CURRENT_DATE
                      AND (r.date_to IS NULL OR r.date_to >= CURRENT_DATE))
             ORDER BY o.id
        """)
        orphans = cr.fetchall()
        if orphans:
            notes.append(
                'no effective rule for %s offering default route(s), so the '
                'default was not carried over: %s' % (
                    len(orphans),
                    ', '.join('%s / %s' % (sup, prod)
                              for _oid, prod, sup in orphans)))

        # ir.model.data rows for the removed model would otherwise dangle.
        cr.execute("""
            DELETE FROM ir_model_data
             WHERE model = 'product.supplier.offering'
        """)
        cr.execute("DROP TABLE IF EXISTS product_supplier_offering CASCADE")
        notes.append('dropped product_supplier_offering')

    # --- repair routes that lost their master supplier ------------------
    # A route is "direct" precisely when it has no master, so is_direct=False
    # with master_id NULL is internally inconsistent: the row lost its master
    # without the compute re-running, and _get_gms_share would then read it as
    # direct and hand back 100%. Seen on #53's seeded Zoom via Sandler route.
    # Only such inconsistent rows are touched, and only back to what the
    # seeded data says: a route deliberately converted to direct through the
    # ORM carries is_direct=True and is left alone.
    SEEDED_MASTERS = [
        ('route_broadvoice_sandler', 'partner_master_supplier_sandler_partners'),
        ('route_broadvoice_telarus', 'partner_master_supplier_telarus'),
        ('route_zoom_telarus', 'partner_master_supplier_telarus'),
        ('route_zoom_sandler', 'partner_master_supplier_sandler_partners'),
    ]
    repaired = []
    for route_xmlid, master_xmlid in SEEDED_MASTERS:
        route = env.ref('crm_deals.%s' % route_xmlid, raise_if_not_found=False)
        master = env.ref('crm_deals.%s' % master_xmlid,
                         raise_if_not_found=False)
        if route and master and not route.master_id and not route.is_direct:
            route.master_id = master
            repaired.append(route_xmlid)
    if repaired:
        notes.append('restored the master supplier on %s' % ', '.join(repaired))
    # Bring name and is_direct back in line with master_id on every route,
    # in case anything else drifted.
    routes = env['product.supplier.route'].with_context(active_test=False).search([])
    env.add_to_compute(routes._fields['name'], routes)
    env.add_to_compute(routes._fields['is_direct'], routes)
    routes.flush_recordset()

    if _has_column(cr, 'res_partner', 'default_route_id'):
        cr.execute("ALTER TABLE res_partner DROP COLUMN default_route_id")
        notes.append('dropped res_partner.default_route_id')

    if notes:
        env['ir.logging'].sudo().create({
            'name': 'crm_deals.migration', 'type': 'server', 'level': 'INFO',
            'dbname': cr.dbname,
            'message': 'Offerings removed: ' + '; '.join(notes) + '.',
            'path': 'migrations/19.0.1.0.18/post-migration.py',
            'func': 'migrate', 'line': '0',
        })
