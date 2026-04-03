from odoo import fields, models


class GmsMerchantAccount(models.Model):
    _name = "gms.merchant.account"
    _description = "GMS Merchant Account"

    name = fields.Char(required=True)
    customer_account_id = fields.Many2one("gms.customer.account", required=True, ondelete="cascade", index=True)
    source_proposal_merchant_id = fields.Many2one("gms.client.proposal.merchant", ondelete="set null")
    legal_name = fields.Char()
    dba_name = fields.Char()
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one("res.country.state")
    zip = fields.Char()
    country_id = fields.Many2one("res.country")
    state = fields.Selection([
        ("draft", "Draft"),
        ("active", "Active"),
        ("inactive", "Inactive"),
    ], default="draft", required=True)
    active = fields.Boolean(default=True)
