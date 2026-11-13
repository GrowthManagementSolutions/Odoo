from odoo import SUPERUSER_ID, api


def _has_column(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Report any SPIFF step-up before the columns go.

    The step-up is removed and each rule keeps its base ``spiff_multiplier``;
    a rule that actually carried one is named here so the figure is not lost
    silently.
    """
    if not _has_column(cr, 'product_route_rule', 'spiff_step_qty'):
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("""
        SELECT id, spiff_multiplier, spiff_step_qty, spiff_step_multiplier
          FROM product_route_rule
         WHERE COALESCE(spiff_step_qty, 0) > 0
         ORDER BY id
    """)
    stepped = cr.fetchall()
    if stepped:
        env['ir.logging'].sudo().create({
            'name': 'crm_deals.migration', 'type': 'server', 'level': 'INFO',
            'dbname': cr.dbname,
            'message': 'SPIFF step-up removed from %s rule(s); each keeps its '
                       'base multiplier. Dropped: %s' % (
                           len(stepped),
                           ', '.join(
                               'rule id=%s base=%s step=%sx from qty %s'
                               % (rid, base, step_mult, step_qty)
                               for rid, base, step_qty, step_mult in stepped)),
            'path': 'migrations/19.0.1.0.20/pre-migration.py',
            'func': 'migrate', 'line': '0',
        })
