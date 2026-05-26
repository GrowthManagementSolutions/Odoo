from odoo import fields, models


class GmsRecipientStatementLine(models.Model):
    _name = "gms.recipient.statement.line"
    _description = "Recipient Statement Line"

    statement_id = fields.Many2one(
        "gms.recipient.statement",
        required=True,
        ondelete="cascade",
    )

    commission_line_id = fields.Many2one(
        "gms.commission.line",
        string="Commission Line",
    )

    merchant_id = fields.Many2one(
        "res.partner",
        string="Merchant",
    )

    service_id = fields.Many2one(
        "product.product",
        string="Service",
    )

    gross_amount = fields.Monetary()

    commission_rate = fields.Float()

    earning_amount = fields.Monetary()

    adjustment_amount = fields.Monetary(
        help="Negative or positive adjustment",
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )