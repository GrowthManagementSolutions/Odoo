from odoo import SUPERUSER_ID, api

# Columns whose fields were removed. Odoo drops the field's registry row on
# upgrade but leaves the column behind.
_DROPPED = [
    ('product_route_rule', 'spiff_step_qty'),
    ('product_route_rule', 'spiff_step_multiplier'),
    ('crm_deal_line', 'quantity'),
    ('crm_deal_line', 'unit_price'),
    ('crm_deal_line', 'route_overridden'),
    ('crm_deal_line', 'override_reason'),
]


def migrate(cr, version):
    """Drop the removed columns, clear the POC dates, refresh Draft snapshots.

    ``date_from`` is cleared here rather than pre-migrate because the column
    is NOT NULL until the schema update drops ``required=True``.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    notes = []

    for table, column in _DROPPED:
        cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = %s AND column_name = %s
        """, (table, column))
        if cr.fetchone():
            cr.execute('ALTER TABLE %s DROP COLUMN %s' % (table, column))
            notes.append('dropped %s.%s' % (table, column))

    # POC data: every rule and agreement goes open-ended at the start.
    for table in ('product_route_rule', 'product_master_agreement'):
        cr.execute('UPDATE %s SET date_from = NULL WHERE date_from IS NOT NULL'
                   % table)
        if cr.rowcount:
            notes.append('cleared date_from on %s %s row(s)'
                         % (cr.rowcount, table))

    # Refresh the snapshot on every Draft line, now that the rule lookup
    # treats an empty date_from as open-ended.
    env.invalidate_all()
    draft = env['crm.deal.line'].search([
        ('status', '=', 'draft'), ('display_type', '=', False),
    ])
    snapshot_fields = [
        'rule_id', 'recurring_basis', 'residual_rate', 'gms_share',
        'has_gms_share', 'spiff_eligible', 'spiff_multiplier',
        'nrc_margin_type', 'nrc_margin_value',
    ]
    for name in snapshot_fields:
        env.add_to_compute(draft._fields[name], draft)
    draft.flush_recordset()
    draft.invalidate_recordset()
    with_rule = len(draft.filtered('rule_id'))
    with_share = len(draft.filtered('has_gms_share'))
    notes.append('refreshed %s Draft line(s): %s resolve a rule, %s a GMS '
                 'share' % (len(draft), with_rule, with_share))

    env['ir.logging'].sudo().create({
        'name': 'crm_deals.migration', 'type': 'server', 'level': 'INFO',
        'dbname': cr.dbname,
        'message': 'Rule/deal-line simplification: ' + '; '.join(notes) + '.',
        'path': 'migrations/19.0.1.0.20/post-migration.py',
        'func': 'migrate', 'line': '0',
    })
