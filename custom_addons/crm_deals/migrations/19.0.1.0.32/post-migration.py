"""#61 - flag Budget Proposal Ready for the Budget Review Meeting activity.

The same call the post_init_hook makes. It resolves the stage by XML id only
and sets the flag once, so a pipeline reorganised in the UI is left alone.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    flagged = env['crm.stage']._flag_budget_review_stage()
    _logger.info('crm_deals #61: Budget Proposal Ready %s',
                 'flagged for the budget review meeting' if flagged
                 else 'not found or already flagged')
