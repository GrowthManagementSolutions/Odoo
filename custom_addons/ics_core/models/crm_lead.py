from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    ics_vertical = fields.Selection(
        selection=[
            ("msp", "MSP"),
            ("naas", "NaaS"),
            ("cameras", "Cameras"),
            ("voice", "Voice"),
            ("signage", "Signage"),
            ("vdaas", "VDaaS"),
            ("cloud_server", "Cloud Server"),
            ("retail_install", "Retail Install"),
            ("restaurant_install", "Restaurant Install"),
            ("custom_dev", "Custom Dev"),
            ("hardware", "Hardware"),
            ("email", "Email"),
            ("co_managed", "Co-Managed"),
            ("break_fix", "Break/Fix"),
            ("prepaid_hours", "Prepaid Hours"),
            ("websites", "Websites"),
            ("ai_agents", "AI Agents"),
            ("other", "Other"),
        ],
        string="ICS Vertical",
    )

    expected_mrr = fields.Monetary(string="Expected MRR")
    expected_one_time = fields.Monetary(string="Expected One-Time Revenue")
    expected_term_months = fields.Integer(string="Expected Term Months")
    multi_site_flag = fields.Boolean(string="Multi-Site Opportunity")
    site_count_estimate = fields.Integer(string="Estimated Site Count")

    referred_by_id = fields.Many2one(
        "res.partner",
        string="Referred By",
        domain="[('is_referral_partner', '=', True)]",
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    def action_set_won_rainbowman(self):
        for lead in self:
            if lead.company_id and lead.company_id.name == "ICS":
                if not lead.ics_vertical:
                    raise ValidationError("ICS Vertical is required before marking this opportunity Won.")

                if not lead.expected_mrr and not lead.expected_one_time:
                    raise ValidationError(
                        "Expected MRR or Expected One-Time Revenue is required before marking this opportunity Won."
                    )

        return super().action_set_won_rainbowman()