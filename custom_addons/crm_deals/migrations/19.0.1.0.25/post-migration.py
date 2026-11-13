"""#56 - the commission forecast is built only when a lead is won.

Lines that already carry forecast rows are marked as generated, so they are
never built a second time. Pending rows that belong to a lead which is not in
a won stage were generated under the old rule; they are removed and their
lines reset, so the forecast appears when the lead is actually won. Received
rows are never deleted.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Commission = env['crm.deal.commission'].sudo()
    Line = env['crm.deal.line'].sudo()

    # 1. Anything with a forecast today has already been generated.
    with_rows = Line.search([('commission_ids', '!=', False)])
    with_rows.write({'forecast_generated': True})

    # 2. Pending rows on leads that are not won should never have existed.
    stale = Commission.search([
        ('status', '=', 'pending'),
        ('lead_id.stage_id.is_won', '=', False),
    ])
    stale_lines = stale.deal_line_id
    stale_leads = stale.lead_id
    deleted = len(stale)
    stale.unlink()

    # Reset only the lines left with no rows at all: a line still holding a
    # received or cancelled row keeps its flag, so winning the lead cannot
    # hand it a second schedule.
    reset = stale_lines.filtered(lambda line: not line.commission_ids)
    reset.write({'forecast_generated': False})

    _logger.info(
        'crm_deals #56: %s line(s) marked as generated; %s pending row(s) '
        'deleted across %s lead(s); %s line(s) reset to ungenerated',
        len(with_rows), deleted, len(stale_leads), len(reset))
