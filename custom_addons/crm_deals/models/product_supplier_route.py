from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductSupplierRoute(models.Model):
    _name = 'product.supplier.route'
    _description = 'Supplier Route'
    _inherit = ['mail.thread']
    _order = 'supplier_id, master_id, id'

    name = fields.Char(
        string='Route',
        compute='_compute_name',
        store=True,
    )
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=True,
        index=True,
        domain=lambda self: self.env['res.partner']._domain_tagged(
            'crm_deals.partner_category_supplier'),
    )
    master_id = fields.Many2one(
        'res.partner',
        string='Master Supplier',
        index='btree_not_null',
        tracking=True,
        domain=lambda self: self.env['res.partner']._domain_tagged(
            'crm_deals.partner_category_master_supplier'),
        help="Leave empty when GMS sells this supplier directly.",
    )
    is_direct = fields.Boolean(
        string='Direct',
        compute='_compute_name',
        store=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help="Archive a route GMS no longer sells through. It stays on the "
             "deal lines that already use it but cannot be picked on new ones.",
    )
    contract_prepared_by = fields.Selection(
        selection=[
            ('sa', 'GMS Solution Architect'),
            ('supplier', 'Supplier'),
        ],
        string='Contract Prepared By',
        required=True,
        default='supplier',
        tracking=True,
        help="Groundwork for later automation. For now the Solution Architect "
             "receives the contract activity either way.",
    )
    supplier_contact_id = fields.Many2one(
        'res.partner',
        string='Supplier Contact',
        domain="[('parent_id', '=', supplier_id)]",
        help="For later automation; nothing reads it yet.",
    )
    master_contact_id = fields.Many2one(
        'res.partner',
        string='Master Contact',
        domain="[('parent_id', '=', master_id)]",
        help="For later automation; nothing reads it yet.",
    )
    gms_share_today = fields.Float(
        string="GMS Share (today)",
        digits=(16, 6),
        compute='_compute_gms_share_today',
    )
    has_gms_share_today = fields.Boolean(compute='_compute_gms_share_today')
    rule_ids = fields.One2many(
        'product.route.rule',
        'route_id',
        string='Product Rules',
    )
    rule_count = fields.Integer(string='Rules', compute='_compute_rule_count')
    notes = fields.Text(string='Notes')

    @api.depends('supplier_id', 'master_id')
    def _compute_name(self):
        for route in self:
            route.is_direct = not route.master_id
            supplier = route.supplier_id.name or ''
            if route.master_id:
                route.name = _('%(supplier)s via %(master)s',
                               supplier=supplier,
                               master=route.master_id.name)
            else:
                route.name = _('%(supplier)s – Direct', supplier=supplier)

    @api.depends('master_id', 'is_direct')
    def _compute_gms_share_today(self):
        """Today's share, for display only.

        Deal lines call ``_get_gms_share(date)`` with the deal's own date, so
        a later agreement never rewrites a past estimate.
        """
        for route in self:
            share = route._get_gms_share()
            route.has_gms_share_today = share is not False
            route.gms_share_today = share or 0.0

    @api.depends('rule_ids')
    def _compute_rule_count(self):
        data = self.env['product.route.rule']._read_group(
            domain=[('route_id', 'in', self.ids)],
            groupby=['route_id'], aggregates=['__count'])
        mapped = {route.id: count for route, count in data}
        for route in self:
            route.rule_count = mapped.get(route.id, 0)

    @api.onchange('supplier_id')
    def _onchange_supplier_id(self):
        """A contact of the old supplier cannot stay on the route."""
        if self.supplier_contact_id.parent_id != self.supplier_id:
            self.supplier_contact_id = False

    @api.onchange('master_id')
    def _onchange_master_id(self):
        if self.master_contact_id.parent_id != self.master_id:
            self.master_contact_id = False

    @api.constrains('supplier_id', 'master_id')
    def _check_unique_pair(self):
        """One route per (supplier, master), direct counting as one.

        Enforced in Python rather than by an SQL unique index, because
        Postgres treats every NULL master as distinct and would let any number
        of direct routes through. Archived routes are included, so archiving a
        route does not free its pair up for a duplicate.
        """
        for route in self:
            duplicate = self.with_context(active_test=False).search([
                ('id', '!=', route.id),
                ('supplier_id', '=', route.supplier_id.id),
                ('master_id', '=', route.master_id.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "A route for %(route)s already exists%(archived)s.",
                    route=route.name,
                    archived=_(" (archived)") if not duplicate.active else '',
                ))

    def _get_gms_share(self, date=None):
        """GMS's share of the residual on ``date``.

        100% on a direct route - there is no master taking a cut. Otherwise
        the master's agreement for that date, or ``False`` when it has none,
        which callers must treat as "unknown", not as zero.
        """
        self.ensure_one()
        if self.is_direct or not self.master_id:
            return 1.0
        return self.master_id._get_gms_share(date)

    def _get_rule(self, product_tmpl, date=None):
        """The one rule effective on ``date`` for this route and product."""
        self.ensure_one()
        date = date or fields.Date.context_today(self)
        return self.env['product.route.rule'].search([
            ('route_id', '=', self.id),
            ('product_tmpl_id', '=', product_tmpl.id),
            '|', ('date_from', '=', False), ('date_from', '<=', date),
            '|', ('date_to', '=', False), ('date_to', '>=', date),
        ], order='date_from desc', limit=1)

    # Rule XML ids that are the default route for their product and supplier,
    # for the seeded demo set.
    _DEFAULT_RULE_SEED = (
        'crm_deals.rule_broadvoice_sandler_ucaas',
        'crm_deals.rule_zoom_telarus_ucaas',
        'crm_deals.rule_square_direct_pos',
        'crm_deals.rule_square_direct_payment_processing',
        'crm_deals.rule_cci_direct_ucaas',
        'crm_deals.rule_cci_direct_best_effort_internet',
        'crm_deals.rule_cci_direct_ethernet_fiber_metro_e',
    )

    @api.model
    def _seed_default_route_rules(self):
        """Flag the seeded rules that are their product's default route.

        Called from data/product_supplier_route_data.xml outside the noupdate
        block, because noupdate skips a record that already exists and so the
        data file alone cannot set the flag on an upgrading database. Only
        applied when that product and supplier have no default yet, so a
        choice made by a user is never overwritten.
        """
        Rule = self.env['product.route.rule']
        for xmlid in self._DEFAULT_RULE_SEED:
            rule = self.env.ref(xmlid, raise_if_not_found=False)
            if not rule or rule.is_default:
                continue
            existing = Rule.search_count([
                ('is_default', '=', True),
                ('product_tmpl_id', '=', rule.product_tmpl_id.id),
                ('supplier_id', '=', rule.supplier_id.id),
            ])
            if not existing:
                rule.is_default = True