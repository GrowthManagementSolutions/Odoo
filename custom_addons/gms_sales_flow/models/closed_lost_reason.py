from odoo import fields, models


class GmsClosedLostReason(models.Model):
    _name = "gms.closed.lost.reason"
    _description = "GMS Closed Lost Reason"
    _order = "sequence, name"

    name = fields.Char(
        string="Reason",
        required=True,
    )

    sequence = fields.Integer(
        default=10,
    )

    active = fields.Boolean(
        default=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )