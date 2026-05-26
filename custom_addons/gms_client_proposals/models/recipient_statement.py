from odoo import api, fields, models


class GmsRecipientStatement(models.Model):
    _name = "gms.recipient.statement"
    _description = "Recipient Statement"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Statement Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
    )

    recipient_id = fields.Many2one(
        "res.partner",
        string="Recipient",
        required=True,
    )

    payout_batch_id = fields.Many2one(
        "gms.payout.batch",
        string="Payout Batch",
    )

    statement_month = fields.Date(
        string="Statement Month",
        required=True,
    )

    line_ids = fields.One2many(
        "gms.recipient.statement.line",
        "statement_id",
        string="Statement Lines",
    )

    total_earnings = fields.Monetary(
        compute="_compute_totals",
        store=True,
    )

    total_adjustments = fields.Monetary(
        compute="_compute_totals",
        store=True,
    )

    net_payout = fields.Monetary(
        compute="_compute_totals",
        store=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    state = fields.Selection([
        ("draft", "Draft"),
        ("finalized", "Finalized"),
        ("sent", "Sent"),
    ], default="draft", tracking=True)

    @api.depends(
        "line_ids.earning_amount",
        "line_ids.adjustment_amount",
    )
    def _compute_totals(self):
        for rec in self:
            earnings = sum(rec.line_ids.mapped("earning_amount"))
            adjustments = sum(rec.line_ids.mapped("adjustment_amount"))

            rec.total_earnings = earnings
            rec.total_adjustments = adjustments
            rec.net_payout = earnings + adjustments

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "gms.recipient.statement"
            ) or "New"

        return super().create(vals)

    def action_finalize(self):
        for rec in self:
            if not rec.line_ids:
                continue

            rec.state = "finalized"

    def action_mark_sent(self):
        self.state = "sent"