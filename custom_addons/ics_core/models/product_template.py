from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    required_doc_set = fields.Char(string="Required Document Set")