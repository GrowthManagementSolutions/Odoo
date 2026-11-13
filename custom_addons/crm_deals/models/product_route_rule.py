from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def _ranges_overlap(a_from, a_to, b_from, b_to):
    """Whether two effective-date ranges overlap.

    Either end may be empty and is then open: an empty start reaches back
    forever, an empty end runs on forever. Two ranges miss each other only
    when one provably ends before the other provably begins, which needs both
    of the dates being compared to be set.
    """
    starts_after = b_to and a_from and a_from > b_to
    ends_before = a_to and b_from and a_to < b_from
    return not starts_after and not ends_before


def _fmt(value):
    """Trim a float for display: 6.0 reads as 6, 2.5 stays 2.5."""
    return ('%g' % value) if value else '0'


class ProductRouteRule(models.Model):
    _name = 'product.route.rule'
    _description = 'Route Product Rule'
    _order = 'route_id, product_tmpl_id, date_from desc, id'

    route_id = fields.Many2one(
        'product.supplier.route',
        string='Route',
        required=True,
        ondelete='cascade',
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string='Product',
        required=True,
        index=True,
    )
    supplier_id = fields.Many2one(
        related='route_id.supplier_id',
        string='Supplier',
        store=True,
        index=True,
    )
    # A rule is the only product-to-supplier link: a supplier sells a product
    # when it has a rule on one of that supplier's routes. There is no
    # separate offering model.
    is_default = fields.Boolean(
        string='Default Route',
        help="The route used by default for this product and supplier.",
    )
    # --- Recurring --------------------------------------------------------
    recurring_basis = fields.Selection(
        selection=[
            ('mrc', 'MRC'),
            ('volume', 'Processing Volume'),
            ('none', 'None'),
        ],
        string='Recurring Basis',
        required=True,
        default='mrc',
    )
    residual_rate = fields.Float(
        string='Residual %',
        digits=(16, 6),
        help="Applied to the recurring basis. Stored as a fraction: 0.3 is "
             "30%. May be 0.",
    )
    # --- One-time, independent of the recurring part ----------------------
    spiff_eligible = fields.Boolean(
        string='SPIFF Eligible',
        default=True,
        help="Untick for charges excluded from SPIFF, such as phone rentals.",
    )
    spiff_multiplier = fields.Float(
        string='SPIFF Multiplier',
        digits=(16, 2),
        default=0.0,
        help="6 means 6x the SPIFF-eligible MRC; 0 means no SPIFF.",
    )
    nrc_margin_type = fields.Selection(
        selection=[
            ('none', 'None'),
            ('percent', 'Percent'),
            ('fixed', 'Fixed Amount'),
        ],
        string='NRC Margin',
        required=True,
        default='none',
    )
    # The stored figure, in the convention the whole module uses: a percent
    # is a fraction (0.1 is 10%), a fixed margin is an amount. It is written
    # through the two helpers below rather than entered directly.
    nrc_margin_value = fields.Float(
        string='NRC Margin Value',
        digits=(16, 6),
        help="A percent margin is stored as a fraction: 0.1 is 10%. A fixed "
             "margin is an amount.",
    )
    # Two non-stored views onto nrc_margin_value, so the figure is entered and
    # read in the right unit for the chosen type: 10% rather than 0.1, and
    # $250 rather than 250. No new column and no data change - each reads the
    # one that matches the type and writes straight back to it.
    nrc_margin_percent = fields.Float(
        string='NRC Margin %',
        digits=(16, 6),
        compute='_compute_nrc_margin_helpers',
        inverse='_inverse_nrc_margin_percent',
    )
    nrc_margin_amount = fields.Monetary(
        string='NRC Margin Amount',
        currency_field='currency_id',
        compute='_compute_nrc_margin_helpers',
        inverse='_inverse_nrc_margin_amount',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.ref('base.USD', raise_if_not_found=False),
        help="Carries the fixed NRC margin. The module is single-currency "
             "USD throughout.",
    )
    # Both dates are optional: an empty date_from means effective from the
    # beginning, an empty date_to means no end.
    date_from = fields.Date(string='Effective From')
    date_to = fields.Date(string='Effective To')
    gms_share = fields.Float(
        string='Share', digits=(16, 6), compute='_compute_rates')
    net_rate = fields.Float(
        string='Net %', digits=(16, 6), compute='_compute_rates')
    spiff_display = fields.Char(string='SPIFF', compute='_compute_displays')
    margin_display = fields.Char(
        string='NRC Margin', compute='_compute_displays')

    @api.depends('route_id', 'residual_rate', 'recurring_basis')
    def _compute_rates(self):
        """Today's share and net rate, for the configuration forms only.

        Deal lines resolve the share against the deal's own date, so neither
        of these is ever the basis of a stored estimate.
        """
        for rule in self:
            share = rule.route_id._get_gms_share() if rule.route_id else False
            rule.gms_share = share or 0.0
            if rule.recurring_basis == 'none':
                rule.net_rate = 0.0
            else:
                rule.net_rate = rule.residual_rate * (share or 0.0)

    @api.depends('recurring_basis', 'spiff_multiplier', 'nrc_margin_type',
                 'nrc_margin_value')
    def _compute_displays(self):
        for rule in self:
            if rule.recurring_basis != 'mrc' or not rule.spiff_multiplier:
                rule.spiff_display = False
            else:
                rule.spiff_display = '%sx' % _fmt(rule.spiff_multiplier)

            if rule.nrc_margin_type == 'percent':
                rule.margin_display = '%s%%' % _fmt(rule.nrc_margin_value * 100)
            elif rule.nrc_margin_type == 'fixed':
                rule.margin_display = '$%s' % _fmt(rule.nrc_margin_value)
            else:
                rule.margin_display = False

    @api.depends('nrc_margin_type', 'nrc_margin_value')
    def _compute_nrc_margin_helpers(self):
        for rule in self:
            is_percent = rule.nrc_margin_type == 'percent'
            is_fixed = rule.nrc_margin_type == 'fixed'
            rule.nrc_margin_percent = rule.nrc_margin_value if is_percent else 0.0
            rule.nrc_margin_amount = rule.nrc_margin_value if is_fixed else 0.0

    def _inverse_nrc_margin_percent(self):
        # Guarded on the type: both helpers are in the arch, so the client
        # sends both, and the one that does not match the type would
        # otherwise write its computed 0 over a good figure.
        for rule in self:
            if rule.nrc_margin_type == 'percent':
                rule.nrc_margin_value = rule.nrc_margin_percent

    def _inverse_nrc_margin_amount(self):
        for rule in self:
            if rule.nrc_margin_type == 'fixed':
                rule.nrc_margin_value = rule.nrc_margin_amount

    @api.onchange('nrc_margin_type')
    def _onchange_nrc_margin_type(self):
        """Drop the old figure when the type changes.

        A percent must never survive as a dollar amount, or the other way
        round. ``write()`` does the same for the API and imports.
        """
        self.nrc_margin_value = 0.0

    def write(self, vals):
        # Same reset outside the form. The helper inverses run after this
        # write, so an amount sent in the very same call still lands.
        if 'nrc_margin_type' in vals and 'nrc_margin_value' not in vals:
            vals = dict(vals, nrc_margin_value=0.0)
        return super().write(vals)

    @api.depends('route_id', 'product_tmpl_id')
    def _compute_display_name(self):
        for rule in self:
            rule.display_name = '%s – %s' % (
                rule.route_id.name or '',
                rule.product_tmpl_id.name or '',
            )

    def _get_spiff_multiplier(self, qty=0):
        """The rule's SPIFF multiplier, or 0 when the basis is not MRC.

        ``qty`` is accepted and ignored: the quantity step-up it used to
        select was removed, and the signature is kept so callers do not have
        to change.
        """
        self.ensure_one()
        return self.spiff_multiplier if self.recurring_basis == 'mrc' else 0.0

    @api.constrains('residual_rate')
    def _check_residual_rate(self):
        for rule in self:
            if not 0 <= rule.residual_rate <= 1:
                raise ValidationError(_(
                    "Residual % must be between 0% and 100%."))

    @api.constrains('spiff_multiplier')
    def _check_spiff(self):
        for rule in self:
            if rule.spiff_multiplier < 0:
                raise ValidationError(_(
                    "The SPIFF Multiplier cannot be negative."))

    @api.constrains('nrc_margin_type', 'nrc_margin_value')
    def _check_nrc_margin(self):
        for rule in self:
            if rule.nrc_margin_type == 'none':
                continue
            if rule.nrc_margin_value < 0:
                raise ValidationError(_(
                    "The NRC Margin cannot be negative."))
            if rule.nrc_margin_type == 'percent' and rule.nrc_margin_value > 1:
                raise ValidationError(_(
                    "A percent NRC Margin cannot exceed 100%."))

    @api.constrains('route_id', 'product_tmpl_id', 'date_from', 'date_to')
    def _check_no_overlap(self):
        """One effective rule per route and product at any given date."""
        for rule in self:
            others = self.search([
                ('id', '!=', rule.id),
                ('route_id', '=', rule.route_id.id),
                ('product_tmpl_id', '=', rule.product_tmpl_id.id),
            ])
            for other in others:
                if _ranges_overlap(rule.date_from, rule.date_to,
                                   other.date_from, other.date_to):
                    raise ValidationError(_(
                        "%(rule)s already has a rule covering these dates "
                        "(from %(other_from)s).",
                        rule=rule.display_name,
                        other_from=other.date_from,
                    ))

    @api.constrains('is_default', 'product_tmpl_id', 'supplier_id',
                    'date_from', 'date_to')
    def _check_single_default(self):
        """At most one default route per product and supplier at a time.

        Two defaults may coexist as long as their date ranges do not overlap,
        so a default can be handed over on a date.
        """
        for rule in self.filtered('is_default'):
            others = self.search([
                ('id', '!=', rule.id),
                ('is_default', '=', True),
                ('product_tmpl_id', '=', rule.product_tmpl_id.id),
                ('supplier_id', '=', rule.supplier_id.id),
            ])
            for other in others:
                if _ranges_overlap(rule.date_from, rule.date_to,
                                   other.date_from, other.date_to):
                    raise ValidationError(_(
                        "%(product)s already has a default route for "
                        "%(supplier)s covering these dates (%(other)s).",
                        product=rule.product_tmpl_id.name,
                        supplier=rule.supplier_id.name,
                        other=other.route_id.name,
                    ))

    def action_copy_to_products(self):
        """Open the wizard that clones this rule onto other products."""
        self.ensure_one()
        return {
            'name': _('Copy to Products'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.route.rule.copy',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_rule_id': self.id},
        }


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    route_rule_ids = fields.One2many(
        'product.route.rule',
        'product_tmpl_id',
        string='Route Rules',
    )
