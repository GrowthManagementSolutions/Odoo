from odoo import fields, models


class GmsCustomerAccount(models.Model):
    _name = "gms.customer.account"
    _description = "GMS Customer Account"

    name = fields.Char(required=True)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict")
    crm_lead_id = fields.Many2one("crm.lead", ondelete="set null")
    source_proposal_id = fields.Many2one("gms.client.proposal", ondelete="set null")
    primary_rep_id = fields.Many2one("res.partner")
    support_manager_id = fields.Many2one("res.partner")
    channel_manager_id = fields.Many2one("res.partner")
    state = fields.Selection([
        ("draft", "Draft"),
        ("active", "Active"),
        ("inactive", "Inactive"),
    ], default="draft", required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
