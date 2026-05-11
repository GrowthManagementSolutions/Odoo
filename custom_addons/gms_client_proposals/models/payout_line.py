from odoo import fields, models


class GMSPayoutLine(models.Model):
    _name = "gms.payout.line"
    _description = "Payout Line"

    batch_id = fields.Many2one(
        "gms.payout.batch",
        required=True,
        ondelete="cascade",
    )

    recipient_id = fields.Many2one(
        "res.partner",
        required=True,
    )

    total_amount = fields.Monetary()

    breakdown_json = fields.Text()

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )