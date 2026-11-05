"""#60 - fill the Med Spa demo templates' Budget Summary Notes.

The two templates are `noupdate="1"` data, so the note added to the data file
is skipped on an upgrade. It is written here instead, and only where the
template carries no note of its own.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.mail import is_html_empty

_logger = logging.getLogger(__name__)

_NOTE = (
    "<p>All figures are estimates based on current supplier pricing and the "
    "information provided. Monthly charges begin when each service is "
    "installed. One-time charges cover equipment and installation. Each "
    "service is provided under its own supplier agreement, which you will "
    "receive separately for signature. This budget summary is valid for 30 "
    "days.</p>"
)
_TEMPLATES = (
    'crm_deals.deal_template_med_spa_communications',
    'crm_deals.deal_template_med_spa_front_desk',
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    filled = 0
    for xml_id in _TEMPLATES:
        template = env.ref(xml_id, raise_if_not_found=False)
        if template and is_html_empty(template.budget_note):
            template.budget_note = _NOTE
            filled += 1
    _logger.info('crm_deals #60: Budget Summary Notes filled on %s demo '
                 'template(s)', filled)
