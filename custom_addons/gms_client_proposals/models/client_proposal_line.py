from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GmsClientProposalLine(models.Model):
    _name = "gms.client.proposal.line"
    _description = "GMS Client Proposal Line"
    _order = "display_order, id"

    display_order = fields.Integer(default=10)

    proposal_id = fields.Many2one(
        "gms.client.proposal",
        required=True,
        ondelete="cascade",
    )

    proposal_merchant_id = fields.Many2one(
        "gms.client.proposal.merchant",
        string="Merchant",
        required=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Solution Category",
        required=True,
        ondelete="restrict",
    )

    supplier_id = fields.Many2one(
        "res.partner",
        domain=[("x_gms_is_supplier", "=", True)],
        ondelete="restrict",
    )

    pricing_model = fields.Selection([
        ("standard", "Standard"),
        ("custom", "Custom"),
    ], default="standard")

    monthly_recurring_fee = fields.Monetary(currency_field="currency_id")
    one_time_fee = fields.Monetary(currency_field="currency_id")
    contract_term_months = fields.Integer(default=12)

    annual_price_equivalent = fields.Monetary(
        compute="_compute_pricing_values",
        store=True,
        currency_field="currency_id",
    )
    line_contract_value = fields.Monetary(
        compute="_compute_pricing_values",
        store=True,
        currency_field="currency_id",
    )

    rate_table_id = fields.Many2one(
        "gms.proposal.rate.table",
        string="Rate Table",
        ondelete="restrict",
    )

    guardrail_status = fields.Selection([
        ("within", "Within Guardrails"),
        ("warning", "Warning"),
        ("outside", "Outside Guardrails"),
    ], compute="_compute_guardrails", store=True)

    requires_review = fields.Boolean(
        compute="_compute_guardrails",
        store=True,
    )

    review_reason = fields.Text(
        compute="_compute_guardrails",
        store=True,
    )

    client_decision_status = fields.Selection([
        ("proposed", "Proposed"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("alternate", "Alternate"),
    ], default="proposed")

    currency_id = fields.Many2one(
        related="proposal_id.currency_id",
        store=True,
        readonly=True,
    )

    _sql_constraints = [
        (
            "unique_line_per_solution",
            "unique(proposal_id, proposal_merchant_id, product_id)",
            "Only one line per Proposal + Merchant + Solution Category is allowed.",
        ),
    ]

    @api.onchange("product_id", "supplier_id", "proposal_id.proposal_date")
    def _onchange_rate_table_id(self):
        for rec in self:
            if not rec.product_id:
                rec.rate_table_id = False
                continue

            proposal_date = rec.proposal_id.proposal_date or fields.Date.today()
            domain = [
                ("product_id", "=", rec.product_id.id),
                ("active", "=", True),
                ("effective_start", "<=", proposal_date),
                "|",
                ("effective_end", "=", False),
                ("effective_end", ">=", proposal_date),
            ]
            if rec.supplier_id:
                domain.append(("supplier_id", "=", rec.supplier_id.id))

            table = self.env["gms.proposal.rate.table"].search(
                domain,
                order="effective_start desc",
                limit=1,
            )
            rec.rate_table_id = table

            if table and not rec.contract_term_months:
                rec.contract_term_months = table.default_contract_term_months or 12

    @api.depends("monthly_recurring_fee", "one_time_fee", "contract_term_months")
    def _compute_pricing_values(self):
        for rec in self:
            monthly = rec.monthly_recurring_fee or 0.0
            one_time = rec.one_time_fee or 0.0
            term = rec.contract_term_months or 0
            rec.annual_price_equivalent = monthly * 12
            rec.line_contract_value = (monthly * term) + one_time

    @api.depends(
        "monthly_recurring_fee",
        "one_time_fee",
        "contract_term_months",
        "rate_table_id",
    )
    def _compute_guardrails(self):
        for rec in self:
            status = "within"
            requires_review = False
            reasons = []

            table = rec.rate_table_id
            if not table:
                rec.guardrail_status = "within"
                rec.requires_review = False
                rec.review_reason = False
                continue

            monthly = rec.monthly_recurring_fee or 0.0
            one_time = rec.one_time_fee or 0.0
            term = rec.contract_term_months or 0

            if table.minimum_monthly_fee and monthly < table.minimum_monthly_fee:
                status = "outside"
                requires_review = True
                reasons.append("Monthly fee below minimum.")
            elif table.target_monthly_fee and monthly < table.target_monthly_fee:
                if status != "outside":
                    status = "warning"
                reasons.append("Monthly fee below target.")

            if table.maximum_monthly_fee and monthly > table.maximum_monthly_fee:
                status = "outside"
                requires_review = True
                reasons.append("Monthly fee above maximum.")

            if table.minimum_one_time_fee and one_time < table.minimum_one_time_fee:
                status = "outside"
                requires_review = True
                reasons.append("One-time fee below minimum.")
            elif table.target_one_time_fee and one_time < table.target_one_time_fee:
                if status != "outside":
                    status = "warning"
                reasons.append("One-time fee below target.")

            if table.maximum_one_time_fee and one_time > table.maximum_one_time_fee:
                status = "outside"
                requires_review = True
                reasons.append("One-time fee above maximum.")

            if table.minimum_contract_term_months and term < table.minimum_contract_term_months:
                status = "outside"
                requires_review = True
                reasons.append("Contract term below minimum.")

            if table.maximum_contract_term_months and term > table.maximum_contract_term_months:
                status = "outside"
                requires_review = True
                reasons.append("Contract term above maximum.")

            if table.approval_required_below_monthly and monthly < table.approval_required_below_monthly:
                requires_review = True
                if status == "within":
                    status = "warning"
                reasons.append("Monthly fee triggers approval review.")

            if table.approval_required_below_one_time and one_time < table.approval_required_below_one_time:
                requires_review = True
                if status == "within":
                    status = "warning"
                reasons.append("One-time fee triggers approval review.")

            if table.approval_required_below_term and term < table.approval_required_below_term:
                requires_review = True
                if status == "within":
                    status = "warning"
                reasons.append("Contract term triggers approval review.")

            rec.guardrail_status = status
            rec.requires_review = requires_review
            rec.review_reason = "\n".join(reasons) if reasons else False