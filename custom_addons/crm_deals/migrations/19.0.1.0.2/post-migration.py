from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Backfill Deal IDs on existing accepted/rejected lines, oldest first."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['crm.deal.line'].search(
        [
            ('status', 'in', ('accepted', 'rejected')),
            ('display_type', '=', False),
            ('deal_ref', '=', False),
        ],
        order='create_date, id',
    )
    sequence = env['ir.sequence']
    for line in lines:
        line.deal_ref = sequence.next_by_code('crm.deal.line')
