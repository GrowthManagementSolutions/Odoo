from odoo import api, fields, models


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

    # ✅ Pricing
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

    # ✅ Rate Table
    rate_table_id = fields.Many2one(
        "gms.proposal.rate.table",
        ondelete="restrict",
    )

    # ✅ Guardrails
    guardrail_status = fields.Selection([
        ("within", "Within"),
        ("warning", "Warning"),
        ("outside", "Outside"),
    ], compute="_compute_guardrails", store=True)

    requires_review = fields.Boolean(
        compute="_compute_guardrails",
        store=True,
    )

    review_reason = fields.Text(
        compute="_compute_guardrails",
        store=True,
    )

    currency_id = fields.Many2one(
        related="proposal_id.currency_id",
        store=True,
        readonly=True,
    )

    client_decision_status = fields.Selection([
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("modified", "Modified"),
        ("removed", "Removed"),
        ("deferred", "Deferred"),
    ], string="Client Decision")

    ack_required = fields.Boolean(
        compute="_compute_ack_required",
        store=True,
    )

    ack_item_id = fields.Many2one("gms.client.proposal.ack.item")

    # =========================
    # COMPUTE: PRICING
    # =========================
    @api.depends("monthly_recurring_fee", "one_time_fee", "contract_term_months")
    def _compute_pricing_values(self):
        for rec in self:
            monthly = rec.monthly_recurring_fee or 0
            one_time = rec.one_time_fee or 0
            term = rec.contract_term_months or 0

            rec.annual_price_equivalent = monthly * 12
            rec.line_contract_value = (monthly * term) + one_time

    # =========================
    # COMPUTE: GUARDRAILS
    # =========================
    @api.depends(
        "monthly_recurring_fee",
        "one_time_fee",
        "contract_term_months",
        "rate_table_id",
    )
    def _compute_guardrails(self):
        for rec in self:
            table = rec.rate_table_id

            status = "within"
            requires = False
            reasons = []

            if not table:
                rec.guardrail_status = "within"
                rec.requires_review = False
                rec.review_reason = False
                continue

            monthly = rec.monthly_recurring_fee or 0
            one_time = rec.one_time_fee or 0
            term = rec.contract_term_months or 0

            # --- Monthly ---
            if table.minimum_monthly_fee and monthly < table.minimum_monthly_fee:
                status = "outside"
                requires = True
                reasons.append("Monthly below minimum")

            elif table.target_monthly_fee and monthly < table.target_monthly_fee:
                if status != "outside":
                    status = "warning"
                reasons.append("Monthly below target")

            if table.maximum_monthly_fee and monthly > table.maximum_monthly_fee:
                status = "outside"
                requires = True
                reasons.append("Monthly above maximum")

            # --- One-time ---
            if table.minimum_one_time_fee and one_time < table.minimum_one_time_fee:
                status = "outside"
                requires = True
                reasons.append("One-time below minimum")

            if table.maximum_one_time_fee and one_time > table.maximum_one_time_fee:
                status = "outside"
                requires = True
                reasons.append("One-time above maximum")

            # --- Contract Term ---
            if table.minimum_contract_term_months and term < table.minimum_contract_term_months:
                status = "outside"
                requires = True
                reasons.append("Term too short")

            if table.maximum_contract_term_months and term > table.maximum_contract_term_months:
                status = "outside"
                requires = True
                reasons.append("Term too long")

            # --- Approval Triggers ---
            if table.approval_required_below_monthly and monthly < table.approval_required_below_monthly:
                requires = True
                if status == "within":
                    status = "warning"
                reasons.append("Monthly requires approval")

            if table.approval_required_below_one_time and one_time < table.approval_required_below_one_time:
                requires = True
                if status == "within":
                    status = "warning"
                reasons.append("One-time requires approval")

            if table.approval_required_below_term and term < table.approval_required_below_term:
                requires = True
                if status == "within":
                    status = "warning"
                reasons.append("Term requires approval")

            rec.guardrail_status = status
            rec.requires_review = requires
            rec.review_reason = "\n".join(reasons) if reasons else False

    @api.depends("client_decision_status")
    def _compute_ack_required(self):
        for rec in self:
            rec.ack_required = rec.client_decision_status in ("rejected", "modified", "removed")