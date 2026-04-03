from odoo import api, fields, models


class GmsSupplierService(models.Model):
    _name = "gms.supplier.service"
    _description = "GMS Supplier Service"

    name = fields.Char(compute="_compute_name", store=True)
    merchant_account_id = fields.Many2one("gms.merchant.account", required=True, ondelete="cascade", index=True)
    supplier_id = fields.Many2one(
        "res.partner",
        required=True,
        domain=[("x_gms_is_supplier", "=", True)],
        ondelete="restrict",
    )
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict")
    source_proposal_line_id = fields.Many2one("gms.client.proposal.line", ondelete="set null")
    state = fields.Selection([
        ("draft", "Draft"),
        ("active", "Active"),
        ("inactive", "Inactive"),
    ], default="draft", required=True)
    expected_monthly_fee = fields.Monetary(currency_field="currency_id")
    expected_one_time_fee = fields.Monetary(currency_field="currency_id")
    expected_contract_term_months = fields.Integer()
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id.id, required=True
    )
    active = fields.Boolean(default=True)

    @api.depends("merchant_account_id", "product_id", "supplier_id")
    def _compute_name(self):
        for rec in self:
            parts = [p for p in [rec.merchant_account_id.name, rec.product_id.display_name, rec.supplier_id.display_name] if p]
            rec.name = " - ".join(parts)
