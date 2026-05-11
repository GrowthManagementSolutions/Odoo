from odoo import fields, models
from odoo.exceptions import ValidationError


class GmsClientProposalSection(models.Model):
    _name = "gms.client.proposal.section"
    _description = "GMS Client Proposal Section"
    _order = "sort_order, id"

    proposal_id = fields.Many2one(
        "gms.client.proposal",
        required=True,
        ondelete="cascade",
    )

    template_section_id = fields.Many2one(
        "gms.sow.template.section",
        ondelete="set null",
    )

    section_code = fields.Char()
    title = fields.Char(required=True)
    body_html = fields.Html()

    included = fields.Boolean(default=True)
    editable = fields.Boolean(default=False)

    sort_order = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    def write(self, vals):
        if "body_html" in vals:
            for rec in self:
                if not rec.editable:
                    raise ValidationError("This section is locked and cannot be edited.")
        return super().write(vals)