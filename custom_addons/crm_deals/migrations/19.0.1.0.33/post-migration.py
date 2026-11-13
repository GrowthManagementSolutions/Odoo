"""#62 - set up the Solutions and Agent Channel pipelines, once.

The same call the post_init_hook makes: the default team is renamed, Agent
Channel is created or adopted, and the listed stages get their sequence,
fold, is_won and team_ids. An ir.config_parameter keeps it to one run, so a
later rename or reorder in the UI is never undone (key rule 44).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    done = env['crm.team']._seed_gms_sales_teams()
    _logger.info('crm_deals #62: sales team setup %s',
                 'applied' if done else 'already done, skipped')
