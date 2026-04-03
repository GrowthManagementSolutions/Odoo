from odoo import api, fields, models


class GmsForecastRecord(models.Model):
    _name = "gms.forecast.record"
    _description = "GMS Forecast Record"

    name = fields.Char(compute="_compute_name", store=True)
    customer_account_id = fields.Many2one("gms.customer.account", required=True, ondelete="cascade")
    merchant_account_id = fields.Many2one("gms.merchant.account", required=True, ondelete="cascade")
    supplier_service_id = fields.Many2one("gms.supplier.service", required=True, ondelete="cascade")
    period_month = fields.Date(required=True, index=True)
    forecast_source = fields.Selection([
        ("accepted_proposal", "Accepted Proposal"),
        ("manual", "Manual"),
    ], default="accepted_proposal", required=True)
    expected_recurring_amount = fields.Monetary(currency_field="currency_id")
    expected_one_time_amount = fields.Monetary(currency_field="currency_id")
    expected_contract_term_months = fields.Integer()
    source_proposal_id = fields.Many2one("gms.client.proposal", ondelete="set null")
    source_proposal_line_id = fields.Many2one("gms.client.proposal.line", ondelete="set null")
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id.id, required=True
    )
    active = fields.Boolean(default=True)

    @api.depends("customer_account_id", "merchant_account_id", "period_month")
    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.customer_account_id.name or ''} - {rec.merchant_account_id.name or ''} - {rec.period_month or ''}"
