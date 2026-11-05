from odoo import SUPERUSER_ID, api


def _has_table(cr, table):
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s",
               (table,))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Give existing deal lines the route matching their old supplier pair.

    Archived routes count: a line that was sold through a route GMS no longer
    uses keeps pointing at it, which is exactly what `active` on the route is
    for. Lines whose pair matches no route keep an empty route and are
    reported - they cannot be accepted until one is chosen, which is the new
    rule, not a regression.

    The commission snapshot is deliberately left empty for historical lines.
    A Draft line refreshes it the next time its product, supplier, route,
    quantity or start date changes; an Accepted or Rejected line is frozen and
    keeps the #36 rates it was closed on.
    """
    if not _has_table(cr, 'crm_deals_54_route_backfill'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("SELECT id, supplier_id, master_supplier_id "
               "FROM crm_deals_54_route_backfill")
    rows = cr.fetchall()

    Route = env['product.supplier.route'].with_context(active_test=False)
    routes = {}
    for route in Route.search([]):
        routes.setdefault((route.supplier_id.id, route.master_id.id), route)

    matched = unmatched = 0
    for line_id, supplier_id, master_id in rows:
        route = routes.get((supplier_id, master_id or False))
        if route:
            cr.execute("UPDATE crm_deal_line SET route_id = %s WHERE id = %s",
                       (route.id, line_id))
            matched += 1
        else:
            unmatched += 1

    # master_supplier_id is related to route_id.master_id, so it follows the
    # routes just written.
    lines = env['crm.deal.line'].browse([row[0] for row in rows]).exists()
    env.add_to_compute(lines._fields['master_supplier_id'], lines)
    env.add_to_compute(lines._fields['route_overridden'], lines)
    lines.flush_recordset()

    cr.execute("DROP TABLE crm_deals_54_route_backfill")
    env['ir.logging'].sudo().create({
        'name': 'crm_deals.migration', 'type': 'server', 'level': 'INFO',
        'dbname': cr.dbname,
        'message': 'Deal line routes backfilled: %s line(s) matched a route, '
                   '%s had no route for their supplier/master pair and need '
                   'one chosen by hand.' % (matched, unmatched),
        'path': 'migrations/19.0.1.0.19/post-migration.py',
        'func': 'migrate', 'line': '0',
    })
