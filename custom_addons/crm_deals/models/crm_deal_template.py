from datetime import date

from odoo import api, fields, models


class CrmDealTemplate(models.Model):
    _name = 'crm.deal.template'
    _description = 'CRM Deal Template'
    _order = 'sequence, name, id'

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    industry_id = fields.Many2one(
        'res.partner.industry',
        string='Industry',
        required=True,
    )
    subsector_id = fields.Many2one(
        'res.partner.subsector',
        string='Sub-sector',
        domain="[('industry_id', '=', industry_id)]",
    )
    line_ids = fields.One2many(
        'crm.deal.template.line',
        'template_id',
        string='Template Lines',
        copy=True,
    )
    budget_note = fields.Html(
        string='Budget Summary Notes',
        help="Copied onto a lead when this template is loaded, unless the "
             "lead already carries notes of its own.",
    )

    @api.onchange('industry_id')
    def _onchange_industry_id(self):
        # A sub-sector belongs to a single industry.
        if self.subsector_id.industry_id != self.industry_id:
            self.subsector_id = False

    def _prepare_deal_line_values(self):
        """Values for the crm.deal.line records this template produces.

        Sections/notes are carried over untouched; real lines carry the
        template's own supplier, route, term and amounts (#59).
        """
        self.ensure_one()
        values = []
        for line in self.line_ids:
            if line.display_type:
                values.append({
                    'sequence': line.sequence,
                    'display_type': line.display_type,
                    'name': line.name,
                })
                continue
            # supplier_id / route_id are stored computed fields on the deal
            # line: passing them explicitly means the compute is skipped and
            # the template's choice survives create (#42). crm.deal.line.create
            # replaces a route that cannot price the product on the new line's
            # resolution date with the default rule's route (#54).
            # A layer-only template line produces a deal line with those
            # layers and no product, ready for the user to pick one (#49).
            unit_price = line.unit_price
            monthly = line.estimated_monthly_cost
            # The rack-rate fallback is for a template line that was never
            # given amounts. A volume line is priced on its processing
            # volume, so its zero MRC is deliberate and stands.
            if not unit_price and not monthly and not line.processing_volume \
                    and line.product_id:
                monthly = line.product_id.list_price
            values.append({
                'sequence': line.sequence,
                'name': line.name,
                # The four layers travel with the line; category_id is a stored
                # compute derived from them (#47), so it is not passed.
                'layer_1_categ_id': line.layer_1_categ_id.id,
                'layer_2_categ_id': line.layer_2_categ_id.id,
                'layer_3_categ_id': line.layer_3_categ_id.id,
                'layer_4_categ_id': line.layer_4_categ_id.id,
                'product_id': line.product_id.id,
                'supplier_id': line.supplier_id.id,
                'route_id': line.route_id.id,
                'contract_term': line.contract_term,
                # The template's own figures (#59). The product's list price
                # is only a fallback, for a template line that carries
                # neither a unit price nor an MRC of its own.
                'quantity': line.quantity or 1.0,
                'unit_price': unit_price,
                'estimated_monthly_cost': monthly,
                'estimated_one_time_revenue': line.estimated_one_time_revenue,
                'processing_volume': line.processing_volume,
            })
        return values


class CrmDealTemplateLine(models.Model):
    _name = 'crm.deal.template.line'
    _inherit = ['crm.deal.line.mixin']
    _description = 'CRM Deal Template Line'
    _order = 'sequence, id'

    # Same shape as crm.deal.line's pair, minus status and the cost fields.
    # A template line may stop at a layer when it covers a service area rather
    # than a specific product (#49), so First Layer OR Product is enough.
    _accountable_required_fields = models.Constraint(
        'CHECK(display_type IS NOT NULL OR product_id IS NOT NULL'
        ' OR layer_1_categ_id IS NOT NULL)',
        'A deal template line needs at least a First Layer Service or a Product.',
    )
    _non_accountable_null_fields = models.Constraint(
        'CHECK(display_type IS NULL OR ('
        ' product_id IS NULL AND contract_term IS NULL'
        ' AND layer_1_categ_id IS NULL AND layer_2_categ_id IS NULL'
        ' AND layer_3_categ_id IS NULL AND layer_4_categ_id IS NULL))',
        'Forbidden values on non-accountable deal template line.',
    )

    template_id = fields.Many2one(
        'crm.deal.template',
        string='Deal Template',
        required=True,
        ondelete='cascade',
    )
    # Route details, shown beside Route so the template reads like the deal
    # dialog (#59). Non-stored related fields: unlike the deal line, a
    # template line never needs to freeze them.
    master_supplier_id = fields.Many2one(
        'res.partner',
        string='Master Supplier',
        related='route_id.master_id',
        readonly=True,
    )
    is_direct = fields.Boolean(
        string='Direct',
        related='route_id.is_direct',
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
    )
    # The same amounts as crm.deal.line after #57, so a template can carry a
    # worked example rather than only a rack rate.
    quantity = fields.Float(string='Quantity', default=1.0)
    unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        compute='_compute_unit_price',
        store=True, readonly=False,
        help="Defaults to the product's sales price and stays editable.",
    )
    estimated_monthly_cost = fields.Monetary(
        string='Estimated Monthly Recurring Charges',
        currency_field='currency_id',
        compute='_compute_estimated_monthly_cost',
        store=True, readonly=False,
    )
    estimated_one_time_revenue = fields.Monetary(
        string='Estimated Non-Recurring Charges',
        currency_field='currency_id',
    )
    processing_volume = fields.Monetary(
        string='Estimated Monthly Processing Volume',
        currency_field='currency_id',
    )
    recurring_basis = fields.Selection(
        selection=[
            ('mrc', 'MRC'),
            ('volume', 'Processing Volume'),
            ('none', 'None'),
        ],
        string='Recurring Basis',
        compute='_compute_recurring_basis',
    )

    def _compute_currency_id(self):
        usd = self.env.ref('base.USD')
        for line in self:
            line.currency_id = usd

    @api.depends('product_id')
    def _compute_unit_price(self):
        for line in self:
            if line.display_type or not line.product_id:
                line.unit_price = 0.0
            else:
                line.unit_price = line.product_id.list_price

    @api.depends('quantity', 'unit_price')
    def _compute_estimated_monthly_cost(self):
        for line in self:
            if line.display_type:
                line.estimated_monthly_cost = 0.0
            else:
                line.estimated_monthly_cost = line.quantity * line.unit_price

    def _template_rule(self):
        """The rule this template line prices against, ignoring dates.

        A template sees every rule regardless of effective range (key rule
        39), so when several match, the latest `date_from` wins and an empty
        one comes last.
        """
        self.ensure_one()
        if self.display_type or not self.route_id:
            return self.env['product.route.rule']
        rules = self._effective_rules().filtered(
            lambda rule: rule.route_id.id == self.route_id.id)
        return rules.sorted(
            key=lambda rule: (bool(rule.date_from), rule.date_from or date.min),
            reverse=True)[:1]

    @api.depends('product_id', 'route_id')
    def _compute_recurring_basis(self):
        for line in self:
            line.recurring_basis = line._template_rule().recurring_basis or False

    @api.onchange('product_id')
    def _onchange_product_id_clear_amounts(self):
        """Clearing the product clears the amounts too, as the deal dialog
        does. The mixin's own onchange handles term, supplier and route."""
        if not self.product_id:
            self.quantity = 1.0
            self.unit_price = 0.0
            self.estimated_monthly_cost = 0.0
            self.estimated_one_time_revenue = 0.0
            self.processing_volume = 0.0

    def _valid_field_parameter(self, field, name):
        # The shared mixin marks fields tracking=True for crm.deal.line, which is
        # a mail.thread. This model is not, so accept and ignore the parameter.
        if name == 'tracking':
            return True
        return super()._valid_field_parameter(field, name)
