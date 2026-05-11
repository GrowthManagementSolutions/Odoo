from odoo import fields, models, api


class GMSPayoutBatch(models.Model):
    _name = "gms.payout.batch"
    _description = "Payout Batch"

    name = fields.Char(required=True)

    payout_month = fields.Date(required=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("paid", "Paid"),
    ], default="draft")

    payout_line_ids = fields.One2many(
        "gms.payout.line",
        "batch_id",
    )

    total_payout_amount = fields.Monetary(
        compute="_compute_total",
        store=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends("payout_line_ids.total_amount")
    def _compute_total(self):
        for rec in self:
            rec.total_payout_amount = sum(
                rec.payout_line_ids.mapped("total_amount")
            )

    def action_approve(self):
        self.state = "approved"

    def action_mark_paid(self):
        self.state = "paid"

        earnings = self.env["gms.commission.earning"].search([
            ("payout_batch_id", "=", self.id)
        ])

        earnings.write({
            "payout_status": "paid"
        })