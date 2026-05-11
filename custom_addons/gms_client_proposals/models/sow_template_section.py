from odoo import fields, models


class GmsSowTemplateSection(models.Model):
    _name = "gms.sow.template.section"
    _description = "SOW Template Section"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "gms.sow.template",
        required=True,
        ondelete="cascade"
    )

    sequence = fields.Integer(default=10)

    section_code = fields.Char()
    title = fields.Char(required=True)
    default_text = fields.Text()

    optional = fields.Boolean(default=False)
    editable = fields.Boolean(default=True)