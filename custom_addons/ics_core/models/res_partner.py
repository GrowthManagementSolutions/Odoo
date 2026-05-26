from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_referral_partner = fields.Boolean(string="Referral Partner")
    is_msp_customer = fields.Boolean(string="MSP Customer")
    is_vendor_carrier = fields.Boolean(string="Vendor / Carrier")
    is_site = fields.Boolean(string="Customer Site")

    ics_vertical_interest = fields.Selection(
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
        string="Primary Vertical Interest",
    )

    assigned_account_exec_id = fields.Many2one(
        "res.users",
        string="Assigned Account Executive",
        check_company=True,
    )

    ics_industry = fields.Char(string="Industry")
    site_count = fields.Integer(string="Site Count")

    msa_signed = fields.Boolean(string="MSA Signed")
    msa_signed_date = fields.Date(string="MSA Signed Date")
    msa_sign_envelope_ref = fields.Char(string="MSA Sign Envelope Reference")

    site_code = fields.Char(string="Site Code")
    site_manager_name = fields.Char(string="Site Manager Name")
    site_hours_of_operation = fields.Char(string="Hours of Operation")
    site_type = fields.Selection(
        selection=[
            ("corporate", "Corporate"),
            ("franchise", "Franchise"),
            ("standalone", "Standalone"),
        ],
        string="Site Type",
    )

    @api.constrains("is_msp_customer", "parent_id")
    def _check_msp_customer_parent_only(self):
        for partner in self:
            if partner.is_msp_customer and partner.parent_id:
                raise ValidationError(
                    "MSP Customer can only be enabled on parent customer records, not child site records."
                )