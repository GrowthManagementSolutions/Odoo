from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GmsProposalRateTable(models.Model):
    _name = "gms.proposal.rate.table"
    _description = "GMS Proposal Rate Table"
    _order = "product_id, supplier_id, effective_start desc"

    name = fields.Char(required=True)
    product_id = fields.Many2one(
        "product.product",
        required=True,
        ondelete="restrict",
        index=True,
    )
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
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    notes = fields.Text()

    #_sql_constraints = [
        #(
            #"gms_rate_table_name_company_unique",
            #"unique(name, company_id)",
            #"Rate table name must be unique per company.",
        #),
    #]

    def name_get(self):
        result = []
        for rec in self:
            parts = [rec.name]
            if rec.product_id:
                parts.append(rec.product_id.display_name)
            if rec.supplier_id:
                parts.append(rec.supplier_id.display_name)
            result.append((rec.id, " | ".join(parts)))
        return result

    @api.constrains("effective_start", "effective_end")
    def _check_effective_dates(self):
        for rec in self:
            if rec.effective_end and rec.effective_end < rec.effective_start:
                raise ValidationError(_("Effective End cannot be earlier than Effective Start."))

    @api.constrains(
        "minimum_monthly_fee",
        "target_monthly_fee",
        "maximum_monthly_fee",
        "minimum_one_time_fee",
        "target_one_time_fee",
        "maximum_one_time_fee",
        "minimum_contract_term_months",
        "maximum_contract_term_months",
    )
    def _check_threshold_ranges(self):
        for rec in self:
            if (
                rec.minimum_monthly_fee
                and rec.target_monthly_fee
                and rec.minimum_monthly_fee > rec.target_monthly_fee
            ):
                raise ValidationError(_("Minimum monthly fee cannot be greater than target monthly fee."))

            if (
                rec.target_monthly_fee
                and rec.maximum_monthly_fee
                and rec.target_monthly_fee > rec.maximum_monthly_fee
            ):
                raise ValidationError(_("Target monthly fee cannot be greater than maximum monthly fee."))

            if (
                rec.minimum_one_time_fee
                and rec.target_one_time_fee
                and rec.minimum_one_time_fee > rec.target_one_time_fee
            ):
                raise ValidationError(_("Minimum one-time fee cannot be greater than target one-time fee."))

            if (
                rec.target_one_time_fee
                and rec.maximum_one_time_fee
                and rec.target_one_time_fee > rec.maximum_one_time_fee
            ):
                raise ValidationError(_("Target one-time fee cannot be greater than maximum one-time fee."))

            if (
                rec.minimum_contract_term_months
                and rec.maximum_contract_term_months
                and rec.minimum_contract_term_months > rec.maximum_contract_term_months
            ):
                raise ValidationError(_("Minimum contract term cannot be greater than maximum contract term."))

            if rec.approval_required_below_term and rec.approval_required_below_term < 0:
                raise ValidationError(_("Approval-required-below term cannot be negative."))