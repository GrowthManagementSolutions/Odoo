from odoo import fields, models


class GmsProposalRateTable(models.Model):
    _name = "gms.proposal.rate.table"
    _description = "GMS Proposal Rate Table"
    _order = "product_id, supplier_id, effective_start desc"

    name = fields.Char(required=True)
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict", index=True)
    supplier_id = fields.Many2one(
        "res.partner",
        domain=[("x_gms_is_supplier", "=", True)],
        ondelete="restrict",
        index=True,
    )
    effective_start = fields.Date(required=True)
    effective_end = fields.Date()
    default_contract_term_months = fields.Integer(default=12)

    minimum_monthly_fee = fields.Monetary(currency_field="currency_id")
    target_monthly_fee = fields.Monetary(currency_field="currency_id")
    maximum_monthly_fee = fields.Monetary(currency_field="currency_id")

    minimum_one_time_fee = fields.Monetary(currency_field="currency_id")
    target_one_time_fee = fields.Monetary(currency_field="currency_id")
    maximum_one_time_fee = fields.Monetary(currency_field="currency_id")

    minimum_contract_term_months = fields.Integer(default=1)
    maximum_contract_term_months = fields.Integer(default=60)

    approval_required_below_monthly = fields.Monetary(currency_field="currency_id")
    approval_required_below_one_time = fields.Monetary(currency_field="currency_id")
    approval_required_below_term = fields.Integer()

    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id.id
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    notes = fields.Text()
