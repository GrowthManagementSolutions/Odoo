from odoo import _, api, fields, models
from odoo.exceptions import UserError

CONTRACT_TERM_SELECTION = [
    ('month_to_month', 'Month-to-month'),
    ('6', '6 Months'),
    ('12', '12 Months'),
    ('18', '18 Months'),
    ('24', '24 Months'),
    ('36', '36 Months'),
    ('48', '48 Months'),
    ('60', '60 Months'),
]


class CrmDealLineMixin(models.AbstractModel):
    """Fields and behaviour shared by deal lines and deal template lines.

    Keeping them here means the template line and the real deal line cannot
    drift apart. Status, currency and the cost fields are NOT part of this
    mixin: they only exist on the real deal line.
    """
    _name = 'crm.deal.line.mixin'
    _description = 'CRM Deal Line Mixin'
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Text(string='Description')
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ],
        default=False,
    )
    # Four-layer category selection (#47). The layers replace direct category
    # entry; category_id is derived from them so search, grouping, templates,
    # the portal and reports keep working unchanged.
    layer_1_categ_id = fields.Many2one(
        'product.category', string='First Layer Service', tracking=True)
    layer_2_categ_id = fields.Many2one(
        'product.category', string='Second Layer Service', tracking=True)
    layer_3_categ_id = fields.Many2one(
        'product.category', string='Third Layer Service', tracking=True)
    layer_4_categ_id = fields.Many2one(
        'product.category', string='Fourth Layer Service', tracking=True)
    last_categ_id = fields.Many2one(
        'product.category', string='Selected Service Category',
        compute='_compute_last_categ_id', store=True,
        help="The deepest layer that is set. Drives the product domain.")
    category_id = fields.Many2one(
        'product.category', string='Category', tracking=True,
        compute='_compute_category_id', store=True, readonly=True)
    product_id = fields.Many2one('product.product', string='Product', tracking=True)

    # Non-stored visibility helpers: per layer, whether the chosen category has
    # sub-categories and whether it holds products directly.
    layer_1_has_children = fields.Boolean(compute='_compute_layer_flags')
    layer_1_has_products = fields.Boolean(compute='_compute_layer_flags')
    layer_2_has_children = fields.Boolean(compute='_compute_layer_flags')
    layer_2_has_products = fields.Boolean(compute='_compute_layer_flags')
    layer_3_has_children = fields.Boolean(compute='_compute_layer_flags')
    layer_3_has_products = fields.Boolean(compute='_compute_layer_flags')
    layer_4_has_children = fields.Boolean(compute='_compute_layer_flags')
    layer_4_has_products = fields.Boolean(compute='_compute_layer_flags')
    # Same pair for the deepest layer, so the Product visibility rule reads as
    # one expression instead of a four-way fallback over the layers.
    last_categ_has_children = fields.Boolean(compute='_compute_layer_flags')
    last_categ_has_products = fields.Boolean(compute='_compute_layer_flags')
    supplier_id = fields.Many2one(
        'res.partner', string='Supplier', tracking=True,
        compute='_compute_supplier_id', store=True, readonly=False)
    # The route replaces the master supplier here (#54). master_supplier_id
    # lives on the real deal line only, related to route_id.master_id.
    route_id = fields.Many2one(
        'product.supplier.route', string='Route', tracking=True,
        compute='_compute_route_id', store=True, readonly=False)
    contract_term = fields.Selection(
        selection=CONTRACT_TERM_SELECTION,
        string='Contract Term',
        compute='_compute_contract_term',
        store=True, readonly=False, precompute=True,
        tracking=True,
    )
    allowed_supplier_ids = fields.Many2many(
        'res.partner',
        string='Allowed Suppliers',
        compute='_compute_allowed_route_fields',
    )
    allowed_route_ids = fields.Many2many(
        'product.supplier.route',
        relation='crm_deal_line_mixin_allowed_route_rel',
        string='Allowed Routes',
        compute='_compute_allowed_route_fields',
    )

    LAYER_FIELDS = (
        'layer_1_categ_id', 'layer_2_categ_id',
        'layer_3_categ_id', 'layer_4_categ_id',
    )

    def _deepest_layer(self):
        """The deepest layer currently set, read directly off the fields.

        Used instead of last_categ_id inside onchanges, where the stored
        compute has not necessarily been refreshed yet.
        """
        self.ensure_one()
        return (self.layer_4_categ_id or self.layer_3_categ_id
                or self.layer_2_categ_id or self.layer_1_categ_id)

    @api.depends('display_type', *LAYER_FIELDS)
    def _compute_last_categ_id(self):
        for line in self:
            line.last_categ_id = False if line.display_type \
                else line._deepest_layer()

    @api.depends('last_categ_id')
    def _compute_category_id(self):
        for line in self:
            line.category_id = line.last_categ_id

    @api.depends(*LAYER_FIELDS)
    def _compute_layer_flags(self):
        Product = self.env['product.product']
        for line in self:
            for index in range(1, 5):
                categ = line['layer_%d_categ_id' % index]
                line['layer_%d_has_children' % index] = bool(categ.child_id)
                line['layer_%d_has_products' % index] = bool(categ) and bool(
                    Product.search([('categ_id', '=', categ.id)], limit=1))
            deepest = line._deepest_layer()
            line.last_categ_has_children = bool(deepest.child_id)
            line.last_categ_has_products = bool(deepest) and bool(
                Product.search([('categ_id', '=', deepest.id)], limit=1))

    def _clear_deeper_layers(self, changed_index):
        """Blank every layer below the one that just changed."""
        self.ensure_one()
        for index in range(changed_index + 1, 5):
            self['layer_%d_categ_id' % index] = False

    def _drop_product_outside_category(self):
        """Clear the product once it no longer sits in the deepest layer."""
        self.ensure_one()
        if not self.product_id:
            return
        categ = self._deepest_layer()
        if not categ or self.product_id.categ_id != categ:
            self.product_id = False

    @api.onchange('layer_1_categ_id')
    def _onchange_layer_1_categ_id(self):
        self._clear_deeper_layers(1)
        self._drop_product_outside_category()

    @api.onchange('layer_2_categ_id')
    def _onchange_layer_2_categ_id(self):
        self._clear_deeper_layers(2)
        self._drop_product_outside_category()

    @api.onchange('layer_3_categ_id')
    def _onchange_layer_3_categ_id(self):
        self._clear_deeper_layers(3)
        self._drop_product_outside_category()

    @api.onchange('layer_4_categ_id')
    def _onchange_layer_4_categ_id(self):
        self._drop_product_outside_category()

    @api.model
    def _layer_values_from_product(self, product):
        """Layers 1-4 from the product category's path, top down.

        A category nested deeper than four levels cannot be represented, so the
        path is truncated; last_categ_id would then not equal the product's own
        category. The seeded tree is three levels deep, so this does not arise
        today.
        """
        path = []
        categ = product.categ_id
        while categ:
            path.insert(0, categ)
            categ = categ.parent_id
        values = {}
        for index in range(4):
            values['layer_%d_categ_id' % (index + 1)] = (
                path[index].id if index < len(path) else False)
        return values

    @api.model_create_multi
    def create(self, vals_list):
        Product = self.env['product.product']
        for vals in vals_list:
            if vals.get('display_type'):
                # Non-accountable: no layers, no product.
                for field in self.LAYER_FIELDS:
                    vals[field] = False
                continue
            # Reverse fill for server-side creation (template loader, import,
            # API) that supplies a product but no layers.
            if vals.get('product_id') and not any(
                    vals.get(field) for field in self.LAYER_FIELDS):
                vals.update(self._layer_values_from_product(
                    Product.browse(vals['product_id'])))
        return super().create(vals_list)

    @api.depends('display_type')
    def _compute_contract_term(self):
        """Default the term to month-to-month, except where the UI stages it.

        The add-deal-line dialog on the lead passes
        ``deal_line_no_term_default`` (#48) so the user picks the term and the
        cost fields stay hidden until then. Every other path -- the template
        loader, imports, the API -- keeps the default.
        """
        skip_default = self.env.context.get('deal_line_no_term_default')
        for line in self:
            if line.display_type:
                line.contract_term = False
            elif not line.contract_term and not skip_default:
                line.contract_term = 'month_to_month'

    def _route_resolution_date(self):
        """Date the route rules are resolved against, or False for no filter.

        The real deal line overrides this with its own start date; a template
        line has no date, so it sees every rule regardless of effective range.
        """
        self.ensure_one()
        return False

    def _effective_rule_domain(self):
        """Rules for this line's product, effective on the resolution date."""
        self.ensure_one()
        template = self.product_id.product_tmpl_id
        if not template:
            return [('id', '=', False)]
        domain = [('product_tmpl_id', '=', template.id)]
        date = self._route_resolution_date()
        if date:
            domain += [
                # Both ends are optional and open when empty.
                '|', ('date_from', '=', False), ('date_from', '<=', date),
                '|', ('date_to', '=', False), ('date_to', '>=', date),
            ]
        return domain

    def _effective_rules(self):
        """Effective rules whose route is still active.

        Archived routes are filtered out here rather than by the search, so an
        archived route stays readable on the lines that already use it but can
        never be picked on a new one.
        """
        self.ensure_one()
        if self.display_type or not self.product_id:
            return self.env['product.route.rule']
        rules = self.env['product.route.rule'].search(
            self._effective_rule_domain())
        return rules.filtered(lambda rule: rule.route_id.active)

    @api.depends('product_id', 'supplier_id')
    def _compute_allowed_route_fields(self):
        """Suppliers and routes that can actually price this product.

        A rule is the only product-to-supplier link (#53), so the candidates
        come from the rules rather than the product's vendor list: the
        seller_ids domain from #14 is gone.
        """
        for line in self:
            rules = line._effective_rules()
            line.allowed_supplier_ids = rules.route_id.supplier_id
            line.allowed_route_ids = rules.filtered(
                lambda rule: rule.route_id.supplier_id == line.supplier_id
            ).route_id

    def _default_rule_route(self):
        """Route of the is_default rule for this product and supplier.

        Membership is tested by **id**, never with ``in`` on the recordset: on
        a virtual record the non-stored ``allowed_route_ids`` comes back
        NewId-wrapped, so ``rule.route_id in allowed`` is False even when the
        route is right there. That is what left a new line in the dialog with
        no default route.
        """
        self.ensure_one()
        allowed_ids = set(self.allowed_route_ids.ids)
        if not allowed_ids:
            return self.env['product.supplier.route']
        default = self._effective_rules().filtered(
            lambda rule: rule.is_default and rule.route_id.id in allowed_ids)
        return default[:1].route_id

    def _default_route_id(self):
        """The route of the is_default rule for this product and supplier.

        Empty when there is none. The earlier "else the only allowed route"
        fallback was dropped: the default is now exactly what the is_default
        flag says, so an unflagged supplier leaves the field for the user.
        """
        self.ensure_one()
        return self._default_rule_route()

    # Changing the product clears Supplier and Route (#54): the new product is
    # priced by its own rules, so neither value can be carried over. A
    # template's own choice still survives, because the loader passes
    # supplier_id / route_id explicitly at create, which skips these computes.
    # Manual edits survive because nothing but product_id is a dependency.
    @api.depends('product_id')
    def _compute_supplier_id(self):
        for line in self:
            line.supplier_id = False

    @api.depends('product_id', 'supplier_id')
    def _compute_route_id(self):
        """Keep a route that can still price the product, else default it.

        Changing the product drops a route that has no rule for the new one,
        rather than clearing unconditionally, so a deliberate choice survives
        an edit elsewhere on the line. An empty route then takes the
        is_default rule's route when there is one.
        """
        for line in self:
            # Sections and notes are non-accountable (#20).
            if line.display_type or not line.supplier_id:
                line.route_id = False
                continue
            # _origin, not route_id: reading a stored compute inside its own
            # compute returns empty on a virtual record, which is why a new
            # line in the dialog got no default route at all. _origin is the
            # persisted value, and an empty recordset on a brand-new line -
            # exactly when the default should apply.
            route = line._origin.route_id
            # By id, for the NewId reason spelled out in _default_rule_route.
            if route and route.id not in set(line.allowed_route_ids.ids):
                route = self.env['product.supplier.route']
            line.route_id = route or line._default_route_id()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Clearing the product clears what it drove, so nothing hidden is
        saved. contract_term needs doing by hand: it depends on display_type,
        not on the product."""
        if not self.product_id:
            self.contract_term = False
            self.supplier_id = False
            self.route_id = False

    def write(self, vals):
        if 'display_type' in vals:
            new_type = vals.get('display_type')
            if self.filtered(lambda line: line.display_type != new_type):
                raise UserError(_(
                    "You cannot change the type of a deal line. Instead you "
                    "should delete the current line and create a new line of "
                    "the proper type."
                ))
        return super().write(vals)
