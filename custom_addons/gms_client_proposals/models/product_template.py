from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    x_gms_is_solution_category = fields.Boolean(string="Is Solution Category", default=False)
    x_gms_requires_supplier = fields.Boolean(string="Requires Supplier")
    x_gms_allows_recurring_fee = fields.Boolean(string="Allows Recurring Fee", default=True)
    x_gms_allows_one_time_fee = fields.Boolean(string="Allows One-Time Fee", default=True)
    x_gms_default_contract_term = fields.Integer(string="Default Contract Term (Months)")
    x_gms_proposal_sort_order = fields.Integer(string="Proposal Sort Order", default=10)
    x_gms_solution_category = fields.Selection([
        ("payments", "Payments"),
        ("software", "Software"),
        ("hardware", "Hardware"),
    ], string="GMS Solution Category")