from odoo import api, fields, models


class GMSCommissionEarning(models.Model):
    _name = "gms.commission.earning"
    _description = "GMS Commission Earning"

    name = fields.Char(
        string="Reference",
        compute="_compute_name",
        store=True,
    )

    commission_line_id = fields.Many2one(
        "gms.commission.line",
        string="Commission Line",
        required=True,
    )

    recipient_id = fields.Many2one(
        "res.partner",
        string="Recipient",
        required=True,
    )

    recipient_type = fields.Selection([
        ("partner", "Referral Partner"),
        ("agent", "Independent Agent"),
    ], required=True)

    gross_amount = fields.Monetary(
        string="Gross Revenue",
        related="commission_line_id.revenue_amount",
        store=True,
    )

    commission_rate = fields.Float(string="Commission %")

    commission_amount = fields.Monetary(
        string="Commission Amount",
        compute="_compute_commission_amount",
        store=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    status = fields.Selection([
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("paid", "Paid"),
    ], default="draft")

    @api.depends("gross_amount", "commission_rate")
    def _compute_commission_amount(self):
        for rec in self:
            rec.commission_amount = (
                rec.gross_amount * rec.commission_rate / 100.0
            )

    @api.depends("recipient_id")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                f"Commission - {rec.recipient_id.name}"
                if rec.recipient_id
                else "Commission"
            )