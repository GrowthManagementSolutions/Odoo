from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GmsClientProposalLine(models.Model):
    _name = "gms.client.proposal.line"
    _description = "GMS Client Proposal Line"
    _order = "display_order, id"

    proposal_id = fields.Many2one("gms.client.proposal", required=True, ondelete="cascade", index=True)
    proposal_merchant_id = fields.Many2one(
        "gms.client.proposal.merchant", required=True, ondelete="restrict", index=True
    )
    product_id = fields.Many2one(
        "product.product",
        required=True,
        domain=[("x_gms_is_solution_category", "=", True)],
        ondelete="restrict",
        index=True,
    )
    supplier_id = fields.Many2one(
        "res.partner",
        domain=[("x_gms_is_supplier", "=", True)],
        ondelete="restrict",
    )

    pricing_model = fields.Selection([
        ("monthly_only", "Monthly Only"),
        ("one_time_only", "One-Time Only"),
        ("monthly_and_one_time", "Monthly + One-Time"),
    ], default="monthly_and_one_time", required=True)

    monthly_recurring_fee = fields.Monetary(currency_field="currency_id")
    one_time_fee = fields.Monetary(currency_field="currency_id")
    contract_term_months = fields.Integer(required=True, default=12)
    annual_price_equivalent = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    line_contract_value = fields.Monetary(compute="_compute_amounts", store=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="proposal_id.currency_id", store=True, readonly=True)

    rate_table_id = fields.Many2one("gms.proposal.rate.table", ondelete="set null")
    guardrail_status = fields.Selection([
        ("within_guardrails", "Within Guardrails"),
        ("warning", "Warning"),
        ("outside_guardrails", "Outside Guardrails"),
    ], compute="_compute_guardrail_status", store=True, tracking=True)

    requires_review = fields.Boolean(compute="_compute_requires_review", store=True)
    review_reason = fields.Text(compute="_compute_requires_review", store=True)

    client_decision_status = fields.Selection([
        ("accepted_as_presented", "Accepted as Presented"),
        ("rejected_by_client", "Rejected by Client"),
        ("modified_by_client", "Modified by Client"),
        ("removed_from_final", "Removed from Final"),
    ], default="accepted_as_presented", tracking=True)

    ack_required = fields.Boolean(compute="_compute_ack_required", store=True)
    ack_item_id = fields.Many2one("gms.client.proposal.ack_item", copy=False)

    display_order = fields.Integer(default=10)
    notes_client = fields.Text()
    notes_internal = fields.Text()
    active = fields.Boolean(default=True)

    #_sql_constraints = [
        #(
            #"proposal_line_unique_scope",
            #"unique(proposal_id, proposal_merchant_id, product_id)",
            #"Only one solution category line per merchant per proposal is allowed in MVP.",
        #)
    #]

    @api.depends("monthly_recurring_fee", "one_time_fee", "contract_term_months")
    def _compute_amounts(self):
        for rec in self:
            rec.annual_price_equivalent = (rec.monthly_recurring_fee or 0.0) * 12
            rec.line_contract_value = ((rec.monthly_recurring_fee or 0.0) * (rec.contract_term_months or 0)) + (rec.one_time_fee or 0.0)

    @api.depends(
        "rate_table_id",
        "monthly_recurring_fee",
        "one_time_fee",
        "contract_term_months",
    )
    def _compute_guardrail_status(self):
        for rec in self:
            status = "within_guardrails"
            rt = rec.rate_table_id
            if not rt:
                rec.guardrail_status = "warning"
                continue
            if rt.minimum_monthly_fee and (rec.monthly_recurring_fee or 0.0) < rt.minimum_monthly_fee:
                status = "outside_guardrails"
            if rt.minimum_one_time_fee and (rec.one_time_fee or 0.0) < rt.minimum_one_time_fee:
                status = "outside_guardrails"
            if rt.minimum_contract_term_months and (rec.contract_term_months or 0) < rt.minimum_contract_term_months:
                status = "outside_guardrails"
            rec.guardrail_status = status

    @api.depends("guardrail_status")
    def _compute_requires_review(self):
        for rec in self:
            if rec.guardrail_status == "outside_guardrails":
                rec.requires_review = True
                rec.review_reason = "Pricing or term is outside guardrails."
            else:
                rec.requires_review = False
                rec.review_reason = False

    @api.depends("client_decision_status")
    def _compute_ack_required(self):
        for rec in self:
            rec.ack_required = rec.client_decision_status in (
                "rejected_by_client",
                "modified_by_client",
                "removed_from_final",
            )

    @api.constrains("supplier_id", "product_id")
    def _check_supplier_requirement(self):
        for rec in self:
            if rec.product_id.x_gms_requires_supplier and not rec.supplier_id:
                raise ValidationError("Supplier is required for this solution category.")
