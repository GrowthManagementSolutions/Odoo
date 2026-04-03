from odoo import fields, models


class GmsClientProposalSection(models.Model):
    _name = "gms.client.proposal.section"
    _description = "GMS Client Proposal Section"
    _order = "sort_order, id"

    proposal_id = fields.Many2one(
        "gms.client.proposal",
        string="Proposal",
        required=True,
        ondelete="cascade",
    )
    sort_order = fields.Integer(string="Order", default=10)
    section_code = fields.Char(string="Section Code")
    title = fields.Char(string="Title", required=True)
    body_html = fields.Html(string="Content")
    included = fields.Boolean(string="Included", default=True)
    editable = fields.Boolean(string="Editable", default=True)