from odoo import api, fields, models

from ..models.crm_deal_line import CONTRACT_TERM_SELECTION


class CrmDealLineWizard(models.TransientModel):
    _name = 'crm.deal.line.wizard'
    _description = 'Add Deal Line Wizard'

    lead_id = fields.Many2one(
        'crm.lead',
        string='Opportunity',
        required=True,
        ondelete='cascade',
    )
    category_id = fields.Many2one('product.category', string='Category')
    product_id = fields.Many2one(
        'product.product',
        string='Product/Service',
        required=True,
        domain="[('categ_id', '=', category_id)]",
    )
    allowed_supplier_ids = fields.Many2many(
        'res.partner',
        string='Allowed Suppliers',
        compute='_compute_allowed_supplier_ids',
    )
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        domain="[('id', 'in', allowed_supplier_ids)]",
    )
    master_supplier_id = fields.Many2one('res.partner', string='Master Supplier')
    contract_term = fields.Selection(
        selection=CONTRACT_TERM_SELECTION,
        string='Contract Term',
        default='month_to_month',
        required=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.ref('base.USD'),
        required=True,
    )
    estimated_monthly_cost = fields.Monetary(
        string='Estimated Monthly Cost',
        currency_field='currency_id',
    )
    estimated_one_time_revenue = fields.Monetary(
        string='Estimated One-Time Revenue',
        currency_field='currency_id',
    )

    @api.depends('product_id')
    def _compute_allowed_supplier_ids(self):
        # The vendor list lives on the product's Purchase tab
        # (product.template.seller_ids -> product.supplierinfo.partner_id).
        for wizard in self:
            wizard.allowed_supplier_ids = wizard.product_id.seller_ids.partner_id

    @api.onchange('category_id')
    def _onchange_category_id(self):
        # Changing the category invalidates the product (and therefore the
        # supplier), so clear both to avoid a stale, domain-violating value.
        self.product_id = False
        self.supplier_id = False

    @api.onchange('product_id')
    def _onchange_product_id(self):
        # Changing the product invalidates the supplier.
        self.supplier_id = False

    def action_confirm(self):
        self.ensure_one()
        self.env['crm.deal.line'].create({
            'lead_id': self.lead_id.id,
            'category_id': self.category_id.id,
            'product_id': self.product_id.id,
            'supplier_id': self.supplier_id.id,
            'master_supplier_id': self.master_supplier_id.id,
            'contract_term': self.contract_term,
            'currency_id': self.currency_id.id,
            'estimated_monthly_cost': self.estimated_monthly_cost,
            'estimated_one_time_revenue': self.estimated_one_time_revenue,
        })
        return {'type': 'ir.actions.act_window_close'}
