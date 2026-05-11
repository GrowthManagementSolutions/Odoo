from odoo import fields, models


class GmsCommissionLine(models.Model):
    _name = "gms.commission.line"
    _description = "GMS Commission Line"

    name = fields.Char(string="Description")
    merchant_name = fields.Char(string="Merchant Name")
    supplier_reference = fields.Char(string="Supplier Reference")
    revenue_amount = fields.Monetary(string="Revenue")

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    matched_merchant_id = fields.Many2one("res.partner", string="Matched Merchant")
    matched_customer_id = fields.Many2one("res.partner", string="Matched Customer")
    matched_service_id = fields.Many2one("product.product", string="Matched Service")

    match_status = fields.Selection([
        ("unmatched", "Unmatched"),
        ("partial", "Partial"),
        ("matched", "Matched"),
        ("exception", "Exception"),
    ], default="unmatched")

    match_confidence = fields.Selection([
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ], default="low")

    exception_reason = fields.Char()
    needs_review = fields.Boolean(default=False)

    def action_run_matching(self):
        for line in self:
            merchant = self.env["res.partner"].search([
                ("name", "ilike", line.merchant_name)
            ], limit=1)

            if merchant:
                line.write({
                    "matched_merchant_id": merchant.id,
                    "matched_customer_id": merchant.id,
                    "match_status": "matched",
                    "match_confidence": "high",
                    "needs_review": False,
                    "exception_reason": False,
                })
            else:
                line.write({
                    "match_status": "exception",
                    "match_confidence": "low",
                    "needs_review": True,
                    "exception_reason": "No matching merchant found.",
                })

    def action_generate_earnings(self):
        earning_model = self.env["gms.commission.earning"]

        for rec in self:
            if not rec.matched_customer_id:
                continue

            earning_model.create({
                "commission_line_id": rec.id,
                "recipient_id": rec.matched_customer_id.id,
                "recipient_type": "partner",
                "gross_amount": rec.revenue_amount,
                "commission_rate": 10.0,
            })