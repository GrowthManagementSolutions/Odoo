from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    x_gms_partner_type = fields.Selection([
        ("prospect", "Prospect"),
        ("customer", "Customer"),
        ("supplier", "Supplier"),
        ("direct_rep", "Direct Rep"),
        ("referral_partner", "Referral Partner"),
        ("independent_agent", "Independent Agent"),
        ("channel_manager", "Channel Manager"),
        ("support_manager", "Support Manager"),
        ("other", "Other"),
    ], string="GMS Partner Type", tracking=True)

    x_gms_is_client = fields.Boolean(string="Is Client")
    x_gms_is_supplier = fields.Boolean(string="Is Supplier")
    x_gms_is_commission_recipient = fields.Boolean(string="Is Commission Recipient")
    x_gms_primary_rep_id = fields.Many2one("res.partner", string="Primary Rep")
    x_gms_support_manager_id = fields.Many2one("res.partner", string="Support Manager")
    x_gms_channel_manager_id = fields.Many2one("res.partner", string="Channel Manager")
    x_gms_active_for_proposals = fields.Boolean(string="Active for Proposals", default=True)
