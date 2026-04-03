from odoo import fields, models


class GmsSowTemplate(models.Model):
    _name = "gms.sow.template"
    _description = "GMS SOW Template"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    default_intro = fields.Html()
    default_scope = fields.Html()
    default_assumptions = fields.Html()
    default_exclusions = fields.Html()
    acceptance_block_text = fields.Html()
    section_ids = fields.One2many("gms.sow.template.section", "template_id")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)


class GmsSowTemplateSection(models.Model):
    _name = "gms.sow.template.section"
    _description = "GMS SOW Template Section"
    _order = "sort_order, id"

    template_id = fields.Many2one("gms.sow.template", required=True, ondelete="cascade")
    section_code = fields.Char(required=True)
    title = fields.Char(required=True)
    default_text = fields.Html()
    optional = fields.Boolean(default=True)
    editable = fields.Boolean(default=False)
    sort_order = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("template_section_code_unique", "unique(template_id, section_code)", "Section code must be unique per template."),
    ]