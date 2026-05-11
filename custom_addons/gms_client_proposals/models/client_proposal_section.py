from odoo import fields, models


class GmsClientProposalSection(models.Model):
    _name = "gms.client.proposal.section"
    _description = "Proposal Section"
    _order = "sequence, id"

    proposal_id = fields.Many2one(
        "gms.client.proposal",
        required=True,
        ondelete="cascade"
    )

    template_section_id = fields.Many2one(
        "gms.sow.template.section"
    )

    sequence = fields.Integer(default=10)

    title = fields.Char(required=True)

    included = fields.Boolean(default=True)
    editable = fields.Boolean(default=True)

    edited_text = fields.Text()