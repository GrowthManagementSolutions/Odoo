from odoo import fields, models


class GmsClientProposalMerchant(models.Model):
    _name = "gms.client.proposal.merchant"
    _description = "GMS Client Proposal Merchant"
    _order = "display_order, id"

    proposal_id = fields.Many2one("gms.client.proposal", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    legal_name = fields.Char()
    dba_name = fields.Char()
    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one("res.country.state")
    zip = fields.Char()
    country_id = fields.Many2one("res.country")
    phone = fields.Char()
    email = fields.Char()
    contact_name = fields.Char()
    display_order = fields.Integer(default=10)
    notes = fields.Text()
    active = fields.Boolean(default=True)
