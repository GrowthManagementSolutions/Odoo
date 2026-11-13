import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .crm_deal_line_mixin import CONTRACT_TERM_SELECTION  # noqa: F401

_logger = logging.getLogger(__name__)


class CrmDealLine(models.Model):
    _name = 'crm.deal.line'
    _inherit = ['crm.deal.line.mixin', 'mail.thread', 'mail.activity.mixin']
    _description = 'CRM Deal Line'
    _order = 'sequence, id'
    # Search the deal by either half of its display name.
    _rec_names_search = ['deal_ref', 'product_id.name']

    # Mirrors sale.order.line: a real ("accountable") line needs a product and a
    # status; a section/note line must have those and the amounts blanked out.
    # A layer-only line loaded from a template has no product yet (#49), so
    # First Layer OR Product satisfies the accountable check.
    _accountable_required_fields = models.Constraint(
        'CHECK(display_type IS NOT NULL OR ('
        ' (product_id IS NOT NULL OR layer_1_categ_id IS NOT NULL)'
        ' AND status IS NOT NULL))',
        'A deal line needs at least a First Layer Service or a Product.',
    )
    _non_accountable_null_fields = models.Constraint(
        'CHECK(display_type IS NULL OR ('
        ' product_id IS NULL AND currency_id IS NULL'
        ' AND contract_term IS NULL AND status IS NULL'
        ' AND layer_1_categ_id IS NULL AND layer_2_categ_id IS NULL'
        ' AND layer_3_categ_id IS NULL AND layer_4_categ_id IS NULL'
        ' AND COALESCE(quantity, 0) = 0 AND COALESCE(unit_price, 0) = 0'
        ' AND COALESCE(estimated_monthly_cost, 0) = 0'
        ' AND COALESCE(estimated_one_time_revenue, 0) = 0))',
        'Forbidden values on non-accountable deal line.',
    )
    _quantity_positive = models.Constraint(
        'CHECK(display_type IS NOT NULL OR quantity > 0)',
        'A deal line needs a quantity above zero.',
    )

    lead_id = fields.Many2one(
        'crm.lead',
        string='Opportunity',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    company_id = fields.Many2one(
    'res.company',
    string='Company',
    related='lead_id.company_id',
    store=True,
    readonly=True,
    index=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='lead_id.partner_id',
        store=True,
    )
    # Non-stored: read straight off the lead's stage, so moving the lead in or
    # out of a won stage is reflected without any recomputation.
    lead_is_won = fields.Boolean(
        string='Lead Won',
        related='lead_id.stage_id.is_won',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True, readonly=False, precompute=True,
    )
    estimated_price = fields.Monetary(
        string='Estimated Price',
        currency_field='currency_id',
    )
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        compute='_compute_status',
        store=True, readonly=False, precompute=True,
        tracking=True,
    )
    # Quantity and unit price came back with #57, after the #54 fix round had
    # removed them. A stored compute driven by display_type rather than a
    # static default, like status and currency_id: a static default would fill
    # existing section rows and break the non-accountable constraint.
    quantity = fields.Float(
        string='Quantity',
        compute='_compute_quantity',
        store=True, readonly=False, precompute=True,
        tracking=True,
    )
    unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
        compute='_compute_unit_price',
        store=True, readonly=False,
        tracking=True,
        help="Defaults to the product's sales price and stays editable.",
    )
    # Technical names unchanged so #23, #36 and #37 keep working; only the
    # labels moved to the MRC / NRC wording (#54). Quantity x unit price
    # since #57, but editable, so a lump sum can still be typed in.
    estimated_monthly_cost = fields.Monetary(
        string='Estimated Monthly Recurring Charges',
        currency_field='currency_id',
        compute='_compute_estimated_monthly_cost',
        store=True, readonly=False,
        tracking=True,
    )
    estimated_one_time_revenue = fields.Monetary(
        string='Estimated Non-Recurring Charges',
        currency_field='currency_id',
        tracking=True,
    )
    processing_volume = fields.Monetary(
        string='Estimated Monthly Processing Volume',
        currency_field='currency_id',
        tracking=True,
    )
    # --- Supplier and route (#54) ---
    master_supplier_id = fields.Many2one(
        'res.partner',
        string='Master Supplier',
        related='route_id.master_id',
        store=True,
        readonly=True,
        tracking=True,
    )
    is_direct = fields.Boolean(
        string='Direct',
        related='route_id.is_direct',
    )
    # Drives the lock expressions on the deal form. Related to the lead's own
    # field rather than a second copy of _get_user_partner_type().
    is_leads_admin = fields.Boolean(related='lead_id.is_leads_admin')
    # --- Commission snapshot (#54) ---
    # Stored copies, never related fields: a later rate change or an archived
    # route must not alter a line that already carries a snapshot. Refreshed
    # only while the line is Draft, which is what freezes them afterwards.
    rule_id = fields.Many2one(
        'product.route.rule',
        string='Route Rule',
        compute='_compute_commission_snapshot',
        # Stored but NOT readonly=False: a snapshot is never hand-edited, and
        # an editable computed field rendered in a view can be written back by
        # the client, after which Odoo treats it as manually set and the
        # compute stops restoring it. That is what stranded these at 0.
        store=True,
    )
    recurring_basis = fields.Selection(
        selection=[
            ('mrc', 'MRC'),
            ('volume', 'Processing Volume'),
            ('none', 'None'),
        ],
        string='Recurring Basis',
        compute='_compute_commission_snapshot',
        store=True,
    )
    residual_rate = fields.Float(
        string='Residual %', digits=(16, 6),
        compute='_compute_commission_snapshot',
        store=True,
    )
    gms_share = fields.Float(
        string='GMS Share', digits=(16, 6),
        compute='_compute_commission_snapshot',
        store=True,
    )
    spiff_eligible = fields.Boolean(
        string='SPIFF Eligible',
        compute='_compute_commission_snapshot',
        store=True,
    )
    # The one snapshot field that is deliberately editable (#55): a term or
    # quantity exception is set per line. Key rule 40 otherwise forbids
    # readonly=False on a snapshot field, and this is its only exception —
    # here the "compute stops restoring it" effect *is* the override. It is
    # still replaced when product, supplier, route or the date change, since
    # those retrigger the snapshot compute.
    spiff_multiplier = fields.Float(
        string='SPIFF Multiplier', digits=(16, 2),
        compute='_compute_commission_snapshot',
        store=True, readonly=False,
        tracking=True,
    )
    nrc_margin_type = fields.Selection(
        selection=[
            ('none', 'None'),
            ('percent', 'Percent'),
            ('fixed', 'Fixed Amount'),
        ],
        string='NRC Margin',
        compute='_compute_commission_snapshot',
        store=True,
    )
    nrc_margin_value = fields.Float(
        string='NRC Margin Value', digits=(16, 6),
        compute='_compute_commission_snapshot',
        store=True,
    )
    net_rate = fields.Float(
        string='Net',
        digits=(16, 6),
        compute='_compute_net_rate',
        help="Residual × GMS Share. Temporary: #55 replaces it.",
    )
    start_date = fields.Date(string='Start Date', tracking=True)
    payment_frequency = fields.Selection(
        selection=[
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('annual', 'Annual'),
        ],
        string='Payment Frequency',
        default='monthly',
        tracking=True,
    )
    end_date = fields.Date(
        string='End Date',
        compute='_compute_end_date',
        store=True,
    )
    commission_payer_id = fields.Many2one(
        'res.partner',
        string='Commission Payer',
        compute='_compute_commission_payer_id',
        store=True, readonly=False,
        tracking=True,
    )
    # Both come off the #54 snapshot (#55). Stored and readonly, like every
    # other snapshot-derived figure - key rule 40.
    recurring_commission = fields.Monetary(
        string='Est. Monthly Commission',
        currency_field='currency_id',
        compute='_compute_commissions',
        store=True,
    )
    one_time_commission = fields.Monetary(
        string='Est. One-Time Commission',
        currency_field='currency_id',
        compute='_compute_commissions',
        store=True,
    )
    deal_ref = fields.Char(
        string='Deal ID',
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    commission_ids = fields.One2many(
        'crm.deal.commission', 'deal_line_id', string='Commissions')
    commission_count = fields.Integer(
        string='Commissions', compute='_compute_commission_count')
    contract_prep_requested = fields.Boolean(
        string='Contract Preparation Requested',
        readonly=True,
        copy=False,
        help="Set when the Prepare Contracts activity for this service has "
             "been created, so a second signature never duplicates it.",
    )
    forecast_generated = fields.Boolean(
        string='Forecast Generated',
        readonly=True,
        copy=False,
        help="Set once the commission forecast has been generated for this "
             "line. It is never generated a second time, so rows deleted by "
             "hand do not come back.",
    )
    sign_request_count = fields.Integer(
        string='Signatures',
        compute='_compute_sign_request_count',
    )
    project_id = fields.Many2one('project.project', string='Project', copy=False,
                                 tracking=True)
    task_id = fields.Many2one('project.task', string='Task', copy=False, tracking=True)

    @api.depends('deal_ref', 'product_id')
    def _compute_display_name(self):
        """"<Deal ID> - <Product>", falling back to Draft before the ID exists.

        Deliberately not the ``name`` field, which section lines use as their
        label (#20).
        """
        for line in self:
            product = line.product_id.name
            reference = line.deal_ref or _("Draft")
            if product:
                line.display_name = '%s - %s' % (reference, product)
            else:
                line.display_name = line.deal_ref or reference

    # Section/note lines must carry no status, term or currency. Driving these
    # from display_type (stored, readonly=False) instead of static defaults is
    # how sale.order.line keeps non-accountable lines constraint-clean.
    @api.depends('display_type')
    def _compute_status(self):
        for line in self:
            if line.display_type:
                line.status = False
            elif not line.status:
                line.status = 'draft'

    @api.depends('display_type')
    def _compute_currency_id(self):
        usd = self.env.ref('base.USD')
        for line in self:
            if line.display_type:
                line.currency_id = False
            elif not line.currency_id:
                line.currency_id = usd

    # ------------------------------------------------------------------
    # Sign requests
    # ------------------------------------------------------------------
    def _sign_request_domain(self):
        """sign.request.reference_doc is a Reference field, stored as 'model,id'."""
        self.ensure_one()
        return [('reference_doc', '=', '%s,%s' % (self._name, self.id))]

    @api.depends('deal_ref')
    def _compute_sign_request_count(self):
        # sudo: the count must render even for users without Sign access.
        SignRequest = self.env['sign.request'].sudo()
        for line in self:
            line.sign_request_count = (
                SignRequest.search_count(line._sign_request_domain())
                if isinstance(line.id, int) else 0
            )

    def action_request_signature(self):
        """Open the Sign wizard linked to this deal.

        Passing default_reference_doc is enough for sign to link the request and
        to pre-fill the signer: sign.send.request._get_default_signer() returns
        the reference document's partner_id.
        """
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'sign.action_sign_send_request')
        action['context'] = {
            'default_reference_doc': '%s,%s' % (self._name, self.id),
        }
        action['target'] = 'new'
        return action

    def action_view_sign_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Signatures'),
            'res_model': 'sign.request',
            'view_mode': 'kanban,list,form',
            'domain': self._sign_request_domain(),
        }

    # ------------------------------------------------------------------
    # Master supplier + commission
    # ------------------------------------------------------------------
    @api.depends('start_date', 'contract_term')
    def _compute_end_date(self):
        for line in self:
            term = line.contract_term
            if line.display_type or not line.start_date or not term \
                    or term == 'month_to_month':
                line.end_date = False
            else:
                line.end_date = line.start_date + relativedelta(months=int(term))

    # ------------------------------------------------------------------
    # Route resolution and commission snapshot (#54)
    # ------------------------------------------------------------------
    def _route_resolution_date(self):
        """The line's start date, else the lead's Default Start Date, else today.

        Every route and rate lookup on a deal line resolves against this, never
        against "today", so changing an agreement cannot rewrite a past
        estimate (key rule 37).
        """
        self.ensure_one()
        return (self.start_date or self.lead_id.default_start_date
                or fields.Date.context_today(self))

    @api.depends('display_type')
    def _compute_quantity(self):
        """One by default; never set on a section or note (#20)."""
        for line in self:
            line.quantity = 0.0 if line.display_type else (line.quantity or 1.0)

    @api.depends('product_id')
    def _compute_unit_price(self):
        """The product's rack rate, and editable from there (#57).

        Only a product change restates it, so a price typed by hand - or set
        on a line that stopped at a layer - survives.
        """
        for line in self:
            if line.display_type or not line.product_id:
                line.unit_price = 0.0
            else:
                line.unit_price = line.product_id.list_price

    @api.depends('quantity', 'unit_price')
    def _compute_estimated_monthly_cost(self):
        """MRC is quantity x unit price (#57).

        `readonly=False`, so a figure typed straight into the field stands
        until quantity or unit price move again. This is an input field, not
        part of the commission snapshot, so key rule 40 does not apply.
        """
        for line in self:
            if line.display_type:
                line.estimated_monthly_cost = 0.0
            else:
                line.estimated_monthly_cost = line.quantity * line.unit_price

    @api.depends('residual_rate', 'gms_share', 'recurring_basis')
    def _compute_net_rate(self):
        for line in self:
            if line.recurring_basis == 'none':
                line.net_rate = 0.0
            else:
                line.net_rate = line.residual_rate * line.gms_share

    # The rule-derived half of the snapshot, cleared when no rule matches.
    _RULE_SNAPSHOT_BLANK = {
        'rule_id': False, 'recurring_basis': False, 'residual_rate': 0.0,
        'spiff_eligible': False, 'spiff_multiplier': 0.0,
        'nrc_margin_type': False, 'nrc_margin_value': 0.0,
    }

    def _snapshot_values(self):
        """This line's commission basis.

        The **GMS share comes from the route, not the rule**, so it appears as
        soon as a route is selected: 100% on a direct route, otherwise the
        master's agreement effective on the resolution date, and 0 when there
        is no agreement. The rule only contributes the residual, the SPIFF and
        the NRC margin, and those are cleared when no rule matches.
        """
        self.ensure_one()
        values = dict(self._RULE_SNAPSHOT_BLANK, gms_share=0.0)
        if self.display_type or not self.route_id:
            return values
        date = self._route_resolution_date()
        values['gms_share'] = self.route_id._get_gms_share(date) or 0.0
        if not self.product_id:
            return values
        rule = self.route_id._get_rule(self.product_id.product_tmpl_id, date)
        if not rule:
            return values
        values.update(
            rule_id=rule.id,
            recurring_basis=rule.recurring_basis,
            residual_rate=rule.residual_rate,
            spiff_eligible=rule.spiff_eligible,
            spiff_multiplier=rule._get_spiff_multiplier(),
            nrc_margin_type=rule.nrc_margin_type,
            nrc_margin_value=rule.nrc_margin_value,
        )
        return values

    @api.depends('product_id', 'supplier_id', 'route_id',
                 'start_date', 'lead_id.default_start_date')
    def _compute_commission_snapshot(self):
        for line in self:
            if line.status in ('accepted', 'rejected'):
                # Frozen once the line leaves Draft. A Leads Administrator
                # changing the route on such a line refreshes it from write().
                for name, value in line._snapshot_fields_self().items():
                    line[name] = value
                continue
            for name, value in line._snapshot_values().items():
                line[name] = value

    def _snapshot_fields_self(self):
        """The snapshot as it currently stands, to hold a frozen value in place."""
        self.ensure_one()
        return {
            'rule_id': self.rule_id.id, 'recurring_basis': self.recurring_basis,
            'residual_rate': self.residual_rate, 'gms_share': self.gms_share,
            'spiff_eligible': self.spiff_eligible,
            'spiff_multiplier': self.spiff_multiplier,
            'nrc_margin_type': self.nrc_margin_type,
            'nrc_margin_value': self.nrc_margin_value,
        }

    def _check_ready_to_accept(self):
        """Everything a line needs before it can be Accepted (#54).

        Raised as one error naming every failing line, so a bulk Accept All
        reports the whole set rather than stopping at the first problem.
        A missing rule or GMS share is deliberately **not** blocking: both
        show as warning badges on the line instead.
        """
        problems = []
        for line in self.filtered(lambda l: not l.display_type):
            reasons = []
            if not line.route_id:
                reasons.append(_("no route selected"))
            if line.recurring_basis == 'mrc' \
                    and line.estimated_monthly_cost <= 0:
                reasons.append(_("MRC must be above zero"))
            if line.recurring_basis == 'volume' and line.processing_volume <= 0:
                reasons.append(_("processing volume must be above zero"))
            if reasons:
                problems.append('%s: %s' % (
                    line.display_name or line.product_id.display_name or line.id,
                    ', '.join(reasons)))
        if problems:
            raise UserError(_(
                "These deal lines cannot be accepted yet:\n\n%s",
                '\n'.join('\u2022 %s' % problem for problem in problems),
            ))

    @api.depends('master_supplier_id', 'supplier_id')
    def _compute_commission_payer_id(self):
        for line in self:
            if line.display_type:
                line.commission_payer_id = False
            else:
                line.commission_payer_id = \
                    line.master_supplier_id or line.supplier_id

    def _commission_amounts(self):
        """The two commission figures, from the snapshot and the charges.

        Called by the compute for a Draft line, and directly by the
        Leads-Administrator reroute path and the #55 migration, both of which
        need the figures recomputed on a line whose compute is frozen.
        """
        self.ensure_one()
        if self.display_type:
            return {'recurring_commission': 0.0, 'one_time_commission': 0.0}
        share = self.gms_share
        if self.recurring_basis == 'mrc':
            recurring = self.estimated_monthly_cost * self.residual_rate * share
        elif self.recurring_basis == 'volume':
            recurring = self.processing_volume * self.residual_rate * share
        else:
            recurring = 0.0
        # A SPIFF is gross: the master supplier's share never reduces it, and
        # it exists only on an MRC basis (key rule 36).
        spiff = 0.0
        if self.spiff_eligible and self.recurring_basis == 'mrc':
            spiff = self.estimated_monthly_cost * self.spiff_multiplier
        if self.nrc_margin_type == 'percent':
            nrc = self.estimated_one_time_revenue * self.nrc_margin_value * share
        elif self.nrc_margin_type == 'fixed':
            nrc = self.nrc_margin_value * share
        else:
            nrc = 0.0
        return {
            'recurring_commission': recurring,
            'one_time_commission': spiff + nrc,
        }

    @api.depends('estimated_monthly_cost', 'estimated_one_time_revenue',
                 'processing_volume', 'recurring_basis', 'residual_rate',
                 'gms_share', 'spiff_eligible', 'spiff_multiplier',
                 'nrc_margin_type', 'nrc_margin_value')
    def _compute_commissions(self):
        """Live while Draft, frozen afterwards - the snapshot's own rule."""
        for line in self:
            if line.status in ('accepted', 'rejected'):
                line.recurring_commission = line.recurring_commission
                line.one_time_commission = line.one_time_commission
                continue
            for name, value in line._commission_amounts().items():
                line[name] = value

    # ------------------------------------------------------------------
    # Commission forecast schedule
    # ------------------------------------------------------------------
    # Changing any of these on an accepted line rebuilds its future schedule.
    # Amount changes restate the existing pending rows; schedule changes
    # rebuild the future pending window. Neither ever starts a forecast (#56).
    _COMMISSION_AMOUNT_FIELDS = frozenset({
        'estimated_monthly_cost', 'estimated_one_time_revenue',
        'processing_volume', 'route_id', 'spiff_multiplier',
        'quantity', 'unit_price',
    })
    _COMMISSION_SCHEDULE_FIELDS = frozenset({
        'start_date', 'payment_frequency', 'contract_term',
    })

    def _compute_commission_count(self):
        for line in self:
            line.commission_count = len(line.commission_ids)

    def _commission_period_months(self):
        self.ensure_one()
        from .crm_deal_commission import PERIOD_MONTHS
        return PERIOD_MONTHS.get(self.payment_frequency, 1)

    def _commission_future_pending(self):
        """Pending schedule lines due today or later: the regenerable window."""
        today = fields.Date.context_today(self)
        return self.commission_ids.filtered(
            lambda c: c.status == 'pending' and c.due_date and c.due_date >= today)

    def _prepare_commission_vals(self):
        """Schedule rows for one accepted line."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        base = {
            'deal_line_id': self.id,
            'payer_id': self.commission_payer_id.id,
            'currency_id': self.currency_id.id,
        }
        vals_list = []
        if self.one_time_commission:
            vals_list.append(dict(
                base, commission_type='one_time',
                due_date=self.start_date, expected_amount=self.one_time_commission))
        if self.recurring_commission:
            months = self._commission_period_months()
            # Month-to-month has no end date: keep 12 months of runway.
            horizon = self.end_date or (today + relativedelta(months=12))
            due = self.start_date
            while due <= horizon:
                vals_list.append(dict(
                    base, commission_type='recurring', due_date=due,
                    expected_amount=self.recurring_commission * months))
                due += relativedelta(months=months)
        return vals_list

    def _ready_for_forecast(self):
        """Accepted line, won lead, a start date - and not generated before.

        The forecast is only ever built once per line (#56), so rows a user
        deleted are never recreated by a later pass.
        """
        self.ensure_one()
        return bool(
            not self.display_type
            and not self.forecast_generated
            and self.status == 'accepted'
            and self.start_date
            and self.lead_id.stage_id.is_won
        )

    def _generate_commissions(self):
        """Build the initial commission forecast for GMS deals only."""
        gms_company = self.env['crm.team']._gms_company()

        if not gms_company:
            return True

        Commission = self.env['crm.deal.commission'].sudo()

        for line in self:
            if line.company_id != gms_company:
                continue

            if not line._ready_for_forecast():
                continue
            # Any row already on the line wins: migrated or hand-made rows are
            # never duplicated.
            done_keys = {(c.commission_type, c.due_date)
                         for c in line.commission_ids}
            vals_list = [
                v for v in line._prepare_commission_vals()
                if (v['commission_type'], v['due_date']) not in done_keys
            ]
            if not vals_list:
                continue
            Commission.create(vals_list)
            line.sudo().forecast_generated = True
        return True

    def _gms_commission_lines(self):
        """Return only deal lines belonging to GMS."""
        gms_company = self.env['crm.team']._gms_company()
        if not gms_company:
            return self.browse()
        return self.filtered(
            lambda line: line.company_id == gms_company
        )

    def _refresh_commission_amounts(self):
        """Amount change after generation: restate the pending rows in place.

        Rows are never added back - a deleted row stays deleted - and received
        and cancelled rows are left alone.

        The two commission figures are frozen once a line leaves Draft, so
        they are recomputed here first, from the line's current charges and
        its **frozen snapshot**: a deliberate edit of the MRC, the NRC, the
        volume or the SPIFF multiplier moves the forecast, while a rate or
        share changed on the rule afterwards still cannot (key rule 4).
        """
        for line in self._gms_commission_lines():
            if line.display_type:
                continue
            amounts = {name: value
                       for name, value in line._commission_amounts().items()
                       if line[name] != value}
            if amounts:
                line.sudo().write(amounts)
            rows = line.commission_ids.filtered(lambda c: c.status == 'pending')
            if not rows:
                continue
            months = line._commission_period_months()
            for row in rows:
                amount = (
                    line.one_time_commission if row.commission_type == 'one_time'
                    else line.recurring_commission * months)
                if row.expected_amount != amount:
                    row.sudo().expected_amount = amount
        return True

    def _rebuild_future_commissions(self):
        """Schedule change after generation: rebuild the future pending window.

        Rows a user deleted inside that window do come back - the schedule
        itself moved. Received rows are never touched.
        """
        Commission = self.env['crm.deal.commission'].sudo()
        for line in self._gms_commission_lines():
            if line.display_type or not line.forecast_generated:
                continue
            if line.status != 'accepted' or not line.start_date:
                continue
            line._commission_future_pending().sudo().unlink()
            today = fields.Date.context_today(line)
            wanted = [v for v in line._prepare_commission_vals()
                      if v['due_date'] and v['due_date'] >= today]
            already = line.commission_ids.filtered(
                lambda c: c.status != 'cancelled')
            done_keys = {(c.commission_type, c.due_date) for c in already}
            Commission.create([
                v for v in wanted
                if (v['commission_type'], v['due_date']) not in done_keys
            ])
        return True

    def _extend_month_to_month(self):
        """Daily cron: keep a rolling month-to-month schedule 12 months ahead.

        Only rows dated after the line's latest existing row are added, so a
        gap left by a deleted row is not refilled.
        """
        Commission = self.env['crm.deal.commission'].sudo()
        for line in self._gms_commission_lines():
            if line.display_type or not line.forecast_generated:
                continue
            if line.status != 'accepted' or not line.start_date:
                continue
            dates = [c.due_date for c in line.commission_ids if c.due_date]
            if not dates:
                continue
            latest = max(dates)
            Commission.create([
                v for v in line._prepare_commission_vals()
                if v['commission_type'] == 'recurring' and v['due_date'] > latest
            ])
        return True

    def _cancel_future_commissions(self):
        for line in self._gms_commission_lines():
            line._commission_future_pending().sudo().write({'status': 'cancelled'})
        return True

    def _sync_commissions(self, vals):
        for line in self._gms_commission_lines():
            if line.display_type:
                continue
            if 'status' in vals:
                if line.status == 'rejected':
                    line._cancel_future_commissions()
                    continue
                if line.status == 'accepted':
                    # Gated on the lead being won: accepting a line on an
                    # open lead generates nothing (#56).
                    line._generate_commissions()
                    continue
            if line.status != 'accepted' or not line.forecast_generated:
                continue
            changed = set(vals)
            if self._COMMISSION_SCHEDULE_FIELDS & changed:
                line._rebuild_future_commissions()
            if self._COMMISSION_AMOUNT_FIELDS & changed:
                line._refresh_commission_amounts()
        return True

    def action_view_commissions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Commissions'),
            'res_model': 'crm.deal.commission',
            'view_mode': 'list,pivot,graph,form',
            'domain': [('deal_line_id', '=', self.id)],
            'context': {'default_deal_line_id': self.id},
        }

    # ------------------------------------------------------------------
    # CRUD (mirrors sale.order.line's display_type handling)
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        # Server-side creation (template loader, imports, API) inherits the
        # lead's Default Start Date. Done before super() so no follow-up write
        # is needed, which would otherwise post a tracking message per line.
        # Sections and notes are non-accountable and never get a start date.
        Lead = self.env['crm.lead']
        for vals in vals_list:
            if vals.get('display_type'):
                # Non-accountable: no quantity, price or volume (#20).
                vals.update(quantity=0.0, unit_price=0.0, processing_volume=0.0)
            if vals.get('display_type') or vals.get('start_date'):
                continue
            lead_id = vals.get('lead_id') or self.env.context.get('default_lead_id')
            if not lead_id:
                continue
            default_start = Lead.browse(lead_id).default_start_date
            if default_start:
                vals['start_date'] = default_start
        lines = super().create(vals_list)
        # A route supplied on creation - by the deal template loader (#21) or
        # an import - may not be able to price this product on this line's own
        # resolution date. Fall back to the default rule's route in that case.
        for line in lines:
            if line.route_id and line.route_id.id not in set(
                    line.allowed_route_ids.ids):
                line.route_id = line._default_route_id()
        lines._sync_commissions({'status': True})
        return lines

    def write(self, vals):
        if vals.get('status') == 'accepted':
            # Guarding here rather than on each button covers every path that
            # accepts a line: the row buttons, the deal form, Accept All,
            # imports and the API.
            self.filtered(
                lambda line: line.status != 'accepted')._check_ready_to_accept()
        if vals.get('status') in ('accepted', 'rejected'):
            # Materialise the two commissions while the line is still Draft:
            # _compute_commissions freezes them once the status has moved, so
            # a line accepted before its computes had run would freeze at 0.
            real = self.filtered(lambda line: not line.display_type)
            real.mapped('recurring_commission')
            real.mapped('one_time_commission')
        # A Leads Administrator may still change the route on a line that has
        # left Draft. The snapshot compute is frozen by then, so it is
        # refreshed here and the change is recorded in the chatter.
        reroute = self.env['crm.deal.line']
        old_routes = {}
        if 'route_id' in vals:
            reroute = self.filtered(
                lambda line: not line.display_type
                and line.status in ('accepted', 'rejected')
                and line.route_id.id != vals['route_id'])
            old_routes = {line.id: line.route_id for line in reroute}
        res = super().write(vals)
        for line in reroute:
            # Snapshot first, then the amounts it drives: both computes are
            # frozen on a non-Draft line, so neither follows on its own.
            line.write(line._snapshot_values())
            line.write(line._commission_amounts())
            previous = old_routes.get(line.id)
            line.message_post(body=_(
                "Route changed from %(old)s to %(new)s; the commission basis "
                "was refreshed.",
                old=previous.name if previous else _("none"),
                new=line.route_id.name or _("none"),
            ))
        if vals.get('status') in ('accepted', 'rejected'):
            self._assign_deal_ref()
        if vals.get('status') == 'accepted':
            gms_company = self.env['crm.team']._gms_company()

            won_leads = self.lead_id.filtered(
                lambda lead: (
                    gms_company
                    and lead.company_id == gms_company
                    and lead.stage_id.is_won
                )
            )

            if won_leads:
                won_leads._generate_deal_projects_and_tasks()
        self._sync_commissions(vals)
        return res

    def _assign_deal_ref(self):
        """Stamp a Deal ID the first time a line is accepted or rejected.

        Never stamped on draft or section/note lines, and never reassigned, so
        a line flipping between accepted and rejected keeps its original ID.
        """
        sequence = self.env['ir.sequence']
        for line in self:
            if line.deal_ref or line.display_type:
                continue
            if line.status not in ('accepted', 'rejected'):
                continue
            line.deal_ref = sequence.next_by_code('crm.deal.line')

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        for line in self:
            # Sections and notes are always deletable.
            if line.display_type:
                continue
            if line.status in ('accepted', 'rejected'):
                status_label = dict(
                    self._fields['status']._description_selection(self.env)
                )[line.status]
                raise UserError(_(
                    "You cannot delete the deal line \"%(product)s\" because "
                    "it is %(status)s.",
                    product=line.product_id.display_name,
                    status=status_label,
                ))

    # ------------------------------------------------------------------
    # Project / task generation (mirrors sale_project, against deal lines)
    # ------------------------------------------------------------------
    def _generate_projects_and_tasks(self):
        """Create projects/tasks from these deal lines based on the product's
        ``service_tracking``, mirroring sale_project's behaviour but sourced
        from the deal line and its lead instead of a sale order line.

        Idempotent: lines that already recorded a project or task are skipped,
        so a lead re-entering a won stage does not duplicate anything.

        Returns the deal lines skipped because their product is not a service.
        """
        skipped_non_service = self.env['crm.deal.line']

        # Only GMS deal lines may generate projects or tasks.
        gms_company = self.env['crm.team']._gms_company()

        # Collect eligible lines for project/task generation.
        eligible = []

        for line in self:
            # Never process ICS or other non-GMS companies.
            if not gms_company or line.lead_id.company_id != gms_company:
                continue

            # Skip sections and notes.
            if line.display_type:
                continue

            # Prevent duplicate projects and tasks.
            if line.project_id or line.task_id:
                continue

            product = line.product_id
            tracking = product.service_tracking

            if not tracking or tracking == 'no':
                continue

            if product.type != 'service':
                skipped_non_service |= line
                continue

            eligible.append((line, tracking))

        # Contributing task_in_project lines per lead, ordered the way the list
        # is: the first one carrying a project template supplies it.
        contributing = {}
        for line, tracking in eligible:
            if tracking == 'task_in_project':
                contributing.setdefault(line.lead_id, self.env['crm.deal.line'])
                contributing[line.lead_id] |= line
        # ONE task_in_project project per lead, resolved once per pass.
        lead_projects = {}

        for line, tracking in eligible:
            product = line.product_id
            if tracking == 'task_global_project':
                company = line.lead_id.company_id
                if not company:
                    raise UserError(_(
                        "The opportunity must have a company assigned before "
                        "creating a project or task."
                    ))
                project = product.with_company(company).project_id
                if not project:
                    _logger.warning(
                        "Deal line %s: product %s has service_tracking "
                        "'task_global_project' but no project configured; "
                        "skipping task creation.",
                        line.id, product.display_name,
                    )
                    continue
                line._deal_create_task(project)
            elif tracking == 'project_only':
                line.project_id = line._deal_create_project()
            elif tracking == 'task_in_project':
                lead = line.lead_id
                project = lead_projects.get(lead) or line._find_lead_project()
                if not project:
                    project = line._deal_create_lead_project(
                        contributing[lead].sorted(lambda l: (l.sequence, l.id)))
                lead_projects[lead] = project
                line.project_id = project
                # The task is labelled "<Deal ID> - <Product>". A line created
                # directly as accepted has no Deal ID yet, since the stamp
                # normally happens on the accept write, so stamp it here first.
                line._assign_deal_ref()
                prefix = line.deal_ref or lead.name
                line._deal_create_task(
                    project, name='%s - %s' % (prefix, product.display_name))

        return skipped_non_service

    def _find_lead_project(self):
        """The task_in_project project already generated for this lead, if any.

        There is at most one per lead, so a later pass attaches new tasks to it
        instead of creating a second project. ``project_only`` lines also record
        a project_id, hence the service_tracking check.
        """
        self.ensure_one()
        sibling = self.lead_id.deal_line_ids.filtered(
            lambda l: l.project_id
            and not l.display_type
            and l.product_id.service_tracking == 'task_in_project'
        )[:1]
        return sibling.project_id

    def _deal_create_lead_project(self, contributing_lines):
        """Create the single task_in_project project for this line's lead.

        Named after the lead and owned by its customer. The project template
        comes from the first contributing line by sequence that has one; with
        none, the project is created blank.
        """
        self.ensure_one()
        lead = self.lead_id
        company = lead.company_id
        if not company:
            raise UserError(_(
                "The opportunity must have a company assigned before "
                "creating a project or task."
            ))
        template = next(
            (line.product_id.project_template_id for line in contributing_lines
             if line.product_id.project_template_id),
            self.env['project.project'],
        )
        values = {
            'name': lead.name,
            'partner_id': lead.partner_id.id,
            'company_id': company.id,
        }
        if template:
            if template.is_template:
                project = template.action_create_from_template(values)
            else:
                project = template.copy(values)
            project.tasks.write({'partner_id': lead.partner_id.id})
        else:
            project = self.env['project.project'].create(values)
        return project

    def _deal_create_project(self):
        self.ensure_one()
        lead = self.lead_id
        company = lead.company_id
        if not company:
            raise UserError(_(
                "The opportunity must have a company assigned before "
                "creating a project or task."
        ))
        template = self.product_id.project_template_id
        values = {
            'name': lead.name,
            'partner_id': lead.partner_id.id,
            'company_id': company.id,
        }
        if template:
            values['name'] = '%s - %s' % (lead.name, template.name)
            if template.is_template:
                project = template.action_create_from_template(values)
            else:
                project = template.copy(values)
            project.tasks.write({'partner_id': lead.partner_id.id})
        else:
            values['name'] = '%s - %s' % (lead.name, self.product_id.display_name)
            project = self.env['project.project'].create(values)
        return project

    def _deal_create_task(self, project, name=None):
        """Create the task for this line. ``name`` overrides the default
        ``<lead> - <template or product>`` label; task_in_project passes
        ``<Deal ID> - <Product>``.
        """
        self.ensure_one()
        lead = self.lead_id
        template = self.product_id.task_template_id
        if template:
            values = {
                'name': name or '%s - %s' % (lead.name, template.name),
                'project_id': project.id,
            }
            task_id = template.with_context(
                default_partner_id=lead.partner_id.id,
            ).action_create_from_template(values)
            task = self.env['project.task'].browse(task_id)
        else:
            task = self.env['project.task'].create({
                'name': name or '%s - %s' % (lead.name, self.product_id.display_name),
                'partner_id': lead.partner_id.id,
                'project_id': project.id,
                'company_id': project.company_id.id,
            })
        self.task_id = task
        return task

    @api.onchange('product_id')
    def _onchange_product_id_clear_costs(self):
        """Clear the estimates when the product goes away (#48).

        Separate from the mixin's own product onchange because these two fields
        exist only on the real deal line, not on template lines.
        """
        if not self.product_id:
            # Quantity goes back to its default rather than to zero: a line
            # that stops at a layer is still a real line, and the SQL
            # constraint wants a quantity above zero (#57).
            self.quantity = 1.0
            self.unit_price = 0.0
            self.estimated_monthly_cost = 0.0
            self.estimated_one_time_revenue = 0.0

    def _contract_prep_summary(self):
        """Activity summary for this service (#60)."""
        self.ensure_one()
        return _("Prepare contract: %(deal)s - %(product)s (%(supplier)s)",
                 deal=self.deal_ref or _("Draft"),
                 product=self.product_id.name or self.name or '',
                 supplier=self.supplier_id.name or _("no supplier"))

    def _contract_prep_note(self):
        """Activity body, worded by the route's contract_prepared_by (#60)."""
        self.ensure_one()
        supplier = self.supplier_id.name or _("the supplier")
        customer = self.lead_id.partner_id.display_name or self.lead_id.name or ''
        if self.route_id.contract_prepared_by == 'sa':
            lines = [_("Prepare the %(supplier)s contract for %(customer)s and "
                       "send it for signature.",
                       supplier=supplier, customer=customer)]
        else:
            lines = [_("Request the contract from %(supplier)s for %(customer)s.",
                       supplier=supplier, customer=customer)]
            contact = self.route_id.supplier_contact_id
            if contact:
                lines.append(_(
                    "Supplier contact: %(name)s, %(email)s, %(phone)s",
                    name=contact.name or '', email=contact.email or '',
                    phone=contact.phone or ''))
        details = [
            _("Quantity: %s", '%g' % self.quantity),
            _("Unit Price: %s", self.lead_id.budget_format_amount(self.unit_price)),
        ]
        if self.recurring_basis == 'volume':
            details.append(_("Processing Volume: %s",
                             self.lead_id.budget_format_amount(self.processing_volume)))
        else:
            details.append(_("MRC: %s",
                             self.lead_id.budget_format_amount(self.estimated_monthly_cost)))
        details.append(_("NRC: %s", self.lead_id.budget_format_amount(
            self.estimated_one_time_revenue)))
        details.append(_("Contract Term: %s", dict(
            self._fields['contract_term'].selection).get(self.contract_term, '')
            if self.contract_term else ''))
        return '<p>%s</p><p>%s</p>' % (
            '<br/>'.join(lines), '<br/>'.join(details))


    def action_portal_decision(self, status):
        """Allow budget decisions only for unsigned GMS opportunities."""
        self.ensure_one()

        gms_company = self.env['crm.team']._gms_company()
        lead = self.lead_id

        if not lead or lead.company_id != gms_company:
            raise UserError(_(
                "Budget decisions are available only for GMS opportunities."
            ))

        if lead.budget_signed_on:
            raise UserError(_(
                "This budget has already been signed and cannot be changed."
            ))

        if status not in ('accepted', 'rejected'):
            raise UserError(_("Unknown decision."))

        if self.display_type:
            return False

        if self.status != status:
            self.write({'status': status})
            self.message_post(body=(
                _("Customer accepted this service via the Budget Summary.")
                if status == 'accepted'
                else _("Customer rejected this service via the Budget Summary.")
            ))

        return True

    def action_open_deal_form(self):
        """Open this line in the deal form (#30) in the current window, so the
        breadcrumb leads back to the lead it was opened from."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Deal'),
            'res_model': 'crm.deal.line',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('crm_deals.crm_deal_line_view_form').id, 'form')],
            'target': 'current',
        }

    def action_accept(self):
        self.write({'status': 'accepted'})

    def action_reject(self):
        self.write({'status': 'rejected'})

    # --- Configuration documents (#43) ---
    config_document_count = fields.Integer(
        string='Config Documents',
        compute='_compute_config_document_count',
    )

    def _compute_config_document_count(self):
        data = self.env['config.document']._read_group(
            [('deal_line_id', 'in', self.ids)],
            groupby=['deal_line_id'],
            aggregates=['__count'],
        )
        mapped = {line.id: count for line, count in data}
        for line in self:
            line.config_document_count = mapped.get(line.id, 0)

    def action_view_config_documents(self):
        self.ensure_one()
        return {
            'name': _('Config Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'config.document',
            'view_mode': 'list,kanban,form',
            'domain': [('deal_line_id', '=', self.id)],
            'context': {
                'default_deal_line_id': self.id,
                'default_partner_id': (
                    self.partner_id.commercial_partner_id or self.partner_id).id,
                'default_task_id': self.task_id.id,
            },
        }

    def action_add_config_document(self):
        self.ensure_one()
        return self.env['config.document']._prefill_action({
            'deal_line_id': self.id,
            'partner_id': (self.partner_id.commercial_partner_id or self.partner_id).id,
            'task_id': self.task_id.id,
        })
