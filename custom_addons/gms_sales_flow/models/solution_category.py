from odoo import fields, models


class GmsSolutionCategory(models.Model):
    _name = "gms.solution.category"
    _description = "GMS Solution Category"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
    )

    sequence = fields.Integer(
        default=10,
    )

    active = fields.Boolean(
        default=True,
    )

    parent_id = fields.Many2one(
        comodel_name="gms.solution.category",
        string="Parent Category",
        ondelete="restrict",
        index=True,
    )

    child_ids = fields.One2many(
        comodel_name="gms.solution.category",
        inverse_name="parent_id",
        string="Subcategories",
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )
    