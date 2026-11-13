from odoo import SUPERUSER_ID, api

_SNAPSHOT_FIELDS = [
    'rule_id', 'recurring_basis', 'residual_rate', 'gms_share',
    'spiff_eligible', 'spiff_multiplier', 'nrc_margin_type',
    'nrc_margin_value',
]


def migrate(cr, version):
    """Refresh every Draft snapshot and drop routes that cannot price a line.

    The snapshot fields stopped being ``readonly=False``: as editable computed
    fields rendered in a view they could be written back by the client, after
    which Odoo treated them as set by hand and the compute never restored
    them. That is why lines sat at 0% with a perfectly good rule behind them.
    Making them readonly fixes it going forward, but a stored compute only
    re-runs when a dependency changes, so every Draft line is recomputed here.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    notes = []

    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'crm_deal_line' AND column_name = 'has_gms_share'
    """)
    if cr.fetchone():
        cr.execute('ALTER TABLE crm_deal_line DROP COLUMN has_gms_share')
        notes.append('dropped crm_deal_line.has_gms_share')

    draft = env['crm.deal.line'].search([
        ('status', '=', 'draft'), ('display_type', '=', False),
    ])

    # A route that has no rule for the line's product can no longer be
    # selected, so it is cleared; the compute then puts the is_default rule's
    # route in its place when there is one.
    cleared = []
    for line in draft.filtered('route_id'):
        date = line._route_resolution_date()
        tmpl = line.product_id.product_tmpl_id
        if not tmpl or not line.route_id._get_rule(tmpl, date):
            cleared.append('line %s on "%s" (%s): dropped route %s' % (
                line.id, line.lead_id.name,
                line.product_id.display_name or 'no product',
                line.route_id.name))
            line.route_id = False
    if cleared:
        notes.append('%s route(s) cleared for want of a rule: %s'
                     % (len(cleared), '; '.join(cleared)))

    for name in _SNAPSHOT_FIELDS:
        env.add_to_compute(draft._fields[name], draft)
    draft.flush_recordset()
    draft.invalidate_recordset()
    notes.append('refreshed %s Draft line(s): %s resolve a rule, %s a GMS '
                 'share' % (len(draft), len(draft.filtered('rule_id')),
                            len(draft.filtered('gms_share'))))

    env['ir.logging'].sudo().create({
        'name': 'crm_deals.migration', 'type': 'server', 'level': 'INFO',
        'dbname': cr.dbname,
        'message': 'Snapshot refresh: ' + '; '.join(notes) + '.',
        'path': 'migrations/19.0.1.0.21/post-migration.py',
        'func': 'migrate', 'line': '0',
    })
