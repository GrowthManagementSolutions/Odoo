from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    is_ics_solution_category = fields.Boolean(string="ICS Solution Category")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )