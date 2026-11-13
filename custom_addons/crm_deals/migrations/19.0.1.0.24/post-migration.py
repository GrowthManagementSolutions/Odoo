from odoo import SUPERUSER_ID, api

# Columns whose fields were removed with the #36 rate setup. Odoo drops the
# field's registry row on upgrade but leaves the column behind.
_DROPPED = [
    ('crm_deal_line', 'recurring_commission_rate'),
    ('crm_deal_line', 'one_time_commission_rate'),
    ('product_supplierinfo', 'recurring_commission_rate'),
    ('product_supplierinfo', 'one_time_commission_rate'),
]


def migrate(cr, version):
    """Move the commissions onto the route snapshot and drop the #36 setup.

    Every real line is recomputed through ``_commission_amounts()`` rather
    than ``env.add_to_compute``: the compute freezes on an Accepted or
    Rejected line, so only the direct call reaches those, which is what
    "recompute from the frozen snapshot" needs. The pending forecast is then
    rebuilt once for every accepted line; received rows are never touched.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    notes = []

    lines = env['crm.deal.line'].search([('display_type', '=', False)])
    before = {
        line.id: (line.recurring_commission, line.one_time_commission)
        for line in lines
    }
    for line in lines:
        line.write(line._commission_amounts())
    lines.invalidate_recordset()

    accepted = lines.filtered(lambda l: l.status == 'accepted')
    changed = [
        line for line in accepted
        if before[line.id] != (line.recurring_commission,
                               line.one_time_commission)
    ]
    notes.append(
        '%s line(s) recomputed; %s of the %s accepted line(s) changed amount'
        % (len(lines), len(changed), len(accepted)))
    if changed:
        notes.append('changed: ' + ', '.join(
            'line %s on "%s" %.2f/%.2f -> %.2f/%.2f' % (
                line.id, line.lead_id.name,
                before[line.id][0], before[line.id][1],
                line.recurring_commission, line.one_time_commission)
            for line in changed[:20]))

    # Move existing forecasts onto the new amounts. Pending rows are restated
    # in place; received and cancelled rows are never touched. (#56 replaced
    # the regeneration this used to do - see 19.0.1.0.25.)
    accepted._refresh_commission_amounts()
    notes.append('forecast restated for %s accepted line(s)' % len(accepted))

    for table, column in _DROPPED:
        cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = %s AND column_name = %s
        """, (table, column))
        if cr.fetchone():
            cr.execute('ALTER TABLE %s DROP COLUMN %s' % (table, column))
            notes.append('dropped %s.%s' % (table, column))

    cr.execute("DROP TABLE IF EXISTS product_master_supplier CASCADE")
    cr.execute("""
        DELETE FROM ir_model_data WHERE model = 'product.master.supplier'
    """)
    notes.append('dropped product_master_supplier')

    env['ir.logging'].sudo().create({
        'name': 'crm_deals.migration', 'type': 'server', 'level': 'INFO',
        'dbname': cr.dbname,
        'message': 'Commissions moved onto the route snapshot: '
                   + '; '.join(notes) + '.',
        'path': 'migrations/19.0.1.0.24/post-migration.py',
        'func': 'migrate', 'line': '0',
    })
