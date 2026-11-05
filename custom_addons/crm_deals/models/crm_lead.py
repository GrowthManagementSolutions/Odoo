from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.mail import is_html_empty
from odoo.tools.misc import formatLang
from odoo.tools.safe_eval import safe_eval

from .res_partner import LOCATION_COUNT_SELECTION

class CrmLead(models.Model):
    # portal.mixin brings access_token / access_url, exactly as sale.order
    # carries them, so the Budget Summary opens from a tokenised link without
    # the customer needing a portal account (#58).
    _inherit = ['crm.lead', 'portal.mixin']

    _MAX_SOLUTION_ARCHITECTS = 3

    deal_line_ids = fields.One2many(
        'crm.deal.line',
        'lead_id',
        string='Deal Lines',
    )
    industry_id = fields.Many2one(
        'res.partner.industry',
        string='Industry',
        compute='_compute_industry_id',
        store=True, readonly=False,
    )
    subsector_id = fields.Many2one(
        'res.partner.subsector',
        string='Sub-sector',
        compute='_compute_subsector_id',
        store=True, readonly=False,
        domain="[('industry_id', '=', industry_id)]",
    )
    default_start_date = fields.Date(
        string='Default Start Date',
        default=fields.Date.context_today,
        tracking=True,
        help="Start Date given to deal lines added to this lead from now on. "
             "Changing it leaves existing lines untouched.",
    )
    # Mirrors of the res.partner fields, so a lead can carry them before a
    # contact exists and hand them over when one is created.
    location_count = fields.Selection(
        selection=LOCATION_COUNT_SELECTION,
        string='No. of Locations',
    )
    technology_ids = fields.Many2many(
        'res.partner.technology',
        relation='crm_lead_technology_rel',
        column1='lead_id', column2='technology_id',
        string='Tech Stack',
    )
    # Defaults last applied automatically from the industry / sub-sector.
    # Technical: it exists so an onchange can tell an auto-added technology
    # from one the user picked by hand, and swap out only the former.
    auto_technology_ids = fields.Many2many(
        'res.partner.technology',
        relation='crm_lead_auto_technology_rel',
        column1='lead_id', column2='technology_id',
        string='Auto Tech Stack',
    )
    core_line_of_business = fields.Char(string='Core Line of Business')
    job_title_id = fields.Many2one('res.partner.job.title', string='Title')
    deal_template_id = fields.Many2one(
        'crm.deal.template',
        string='Deal Template',
        domain="['&', ('industry_id', '=', industry_id),"
               " '|', ('subsector_id', '=', False),"
               " ('subsector_id', '=', subsector_id)]",
    )
    lead_type = fields.Selection(
        selection=[
            ('independent_agent', 'Independent Agent'),
            ('referral_partner', 'Referral Partner'),
            ('solution_architect', 'Solution Architect'),
        ],
        string='Lead Type',
        default=lambda self: self._default_lead_type(),
    )
    # Drives the readonly expressions in the view; not stored.
    user_partner_type = fields.Selection(
        selection=[
            ('channel_manager', 'Channel Manager'),
            ('solution_architect', 'Solution Architect'),
            ('leads_admin', 'Leads Administrator'),
        ],
        string="Current User's Partner Type",
        compute='_compute_user_partner_type',
    )
    is_leads_admin = fields.Boolean(compute='_compute_user_partner_type')
    channel_manager_id = fields.Many2one(
        'res.partner',
        string='Channel Manager',
        domain=lambda self: self._domain_partners_tagged(
            'crm_deals.partner_category_channel_manager'),
        default=lambda self: self._default_channel_manager_id(),
    )
    independent_agent_id = fields.Many2one(
        'res.partner',
        string='Independent Agent',
        domain=lambda self: self._domain_partners_tagged(
            'crm_deals.partner_category_independent_agent'),
    )
    referral_partner_id = fields.Many2one(
        'res.partner',
        string='Referral Partner',
        domain=lambda self: self._domain_partners_tagged(
            'crm_deals.partner_category_referral_partner'),
    )
    solution_architect_ids = fields.Many2many(
        'res.partner',
        relation='crm_lead_solution_architect_rel',
        column1='lead_id', column2='partner_id',
        string='Solution Architects',
        domain=lambda self: self._domain_partners_tagged(
            'crm_deals.partner_category_solution_architect'),
        default=lambda self: self._default_solution_architect_ids(),
    )
    portal_submitter_id = fields.Many2one(
        'res.partner',
        string='Submitted By',
        readonly=True,
        copy=False,
        index='btree_not_null',
        help="Portal contact who submitted this lead. Filtering the portal list "
             "on this field means an internal user re-assigning the referral "
             "partner does not hide the lead from its submitter.",
    )
    # --- Customer Budget Summary (#58) ---
    budget_sent_date = fields.Datetime(
        string='Budget Sent On',
        readonly=True, copy=False, tracking=True,
    )
    budget_signature = fields.Binary(
        string='Budget Signature',
        attachment=True, readonly=True, copy=False,
    )
    budget_signed_by = fields.Char(
        string='Budget Signed By',
        readonly=True, copy=False, tracking=True,
    )
    budget_signed_on = fields.Datetime(
        string='Budget Signed On',
        readonly=True, copy=False, tracking=True,
    )
    budget_note = fields.Html(
        string='Budget Summary Notes',
        copy=False,
        help="Shown to the customer under the services on the Budget "
             "Summary. Seeded from the deal template, then edited per lead.",
    )
    # QWeb's rendering context does not carry is_html_empty in every path
    # (the bare ir.qweb render of the document card has none), so the test
    # lives here and both the page and the PDF read this flag.
    budget_note_is_empty = fields.Boolean(
        string='Budget Notes Empty',
        compute='_compute_budget_note_is_empty',
    )
    portal_status = fields.Char(
        string='Portal Status',
        compute='_compute_portal_status',
    )
    portal_is_won = fields.Boolean(
        string='Portal Won',
        compute='_compute_portal_status',
    )
    deal_currency_id = fields.Many2one(
        'res.currency',
        string='Deal Currency',
        compute='_compute_deal_currency_id',
        store=True, precompute=True,
    )
    deal_monthly_total = fields.Monetary(
        string='Monthly Total',
        currency_field='deal_currency_id',
        compute='_compute_deal_totals',
        store=True,
    )
    deal_onetime_total = fields.Monetary(
        string='One-Time Total',
        currency_field='deal_currency_id',
        compute='_compute_deal_totals',
        store=True,
    )
    # Kept editable, but resynced from the deal lines whenever those change.
    expected_revenue = fields.Monetary(
        compute='_compute_expected_revenue', store=True, readonly=False)
    recurring_revenue = fields.Monetary(
        compute='_compute_recurring_revenue', store=True, readonly=False)
    recurring_plan = fields.Many2one(
        compute='_compute_recurring_plan', store=True, readonly=False)
    commission_count = fields.Integer(
        string='Commissions', compute='_compute_commission_count')
    deal_task_count = fields.Integer(
        string='Deal Tasks',
        compute='_compute_deal_work_counts',
    )
    deal_project_count = fields.Integer(
        string='Deal Projects',
        compute='_compute_deal_work_counts',
    )
    # Pipeline kanban counter (#52). Stored, because the card shows it on every
    # record: a non-stored compute would mean a sub-read per card. Sections and
    # notes are excluded, as everywhere else.
    deal_line_count = fields.Integer(
        string='Deal Lines',
        compute='_compute_deal_line_counts',
        store=True,
    )
    deal_line_accepted_count = fields.Integer(
        string='Accepted Deal Lines',
        compute='_compute_deal_line_counts',
        store=True,
    )
    # Short contact names for the pipeline card (#52): res.partner's
    # display_name carries the parent company as a prefix, which is too long
    # for a card, so these expose the bare name. Display helpers only - not
    # stored, and nothing reads them server-side.
    channel_manager_short_name = fields.Char(
        string='Channel Manager Name', compute='_compute_party_short_names')
    independent_agent_short_name = fields.Char(
        string='Independent Agent Name', compute='_compute_party_short_names')
    referral_partner_short_name = fields.Char(
        string='Referral Partner Name', compute='_compute_party_short_names')
    solution_architect_short_names = fields.Char(
        string='Solution Architect Names', compute='_compute_party_short_names')

    @api.depends('deal_line_ids.status', 'deal_line_ids.display_type')
    def _compute_deal_line_counts(self):
        for lead in self:
            lines = lead._get_real_deal_lines()
            lead.deal_line_count = len(lines)
            lead.deal_line_accepted_count = len(
                lines.filtered(lambda line: line.status == 'accepted'))

    @api.depends('channel_manager_id', 'independent_agent_id',
                 'referral_partner_id', 'solution_architect_ids')
    def _compute_party_short_names(self):
        for lead in self:
            lead.channel_manager_short_name = lead.channel_manager_id.name or False
            lead.independent_agent_short_name = lead.independent_agent_id.name or False
            lead.referral_partner_short_name = lead.referral_partner_id.name or False
            lead.solution_architect_short_names = ', '.join(
                lead.solution_architect_ids.mapped('name')) or False

    @api.depends('budget_note')
    def _compute_budget_note_is_empty(self):
        for lead in self:
            lead.budget_note_is_empty = is_html_empty(lead.budget_note)

    @api.depends('stage_id', 'active', 'lost_reason_id')
    def _compute_portal_status(self):
        """Real pipeline stage for the portal.

        Lost leads are archived, so they report Lost rather than the stage they
        were sitting in; won leads keep their stage name and get a badge via
        ``portal_is_won``.
        """
        for lead in self:
            if not lead.active and lead.lost_reason_id:
                lead.portal_status = _("Lost")
                lead.portal_is_won = False
            else:
                lead.portal_status = lead.stage_id.name or ''
                lead.portal_is_won = bool(lead.stage_id.is_won)

    @api.model
    def _get_user_partner_type(self):
        """The current user's Partner Type group, if any.

        Leads Administrator wins, being the permissive role.
        """
        user = self.env.user
        if user.has_group('crm_deals.group_partner_type_leads_admin'):
            return 'leads_admin'
        if user.has_group('crm_deals.group_partner_type_channel_manager'):
            return 'channel_manager'
        if user.has_group('crm_deals.group_partner_type_solution_architect'):
            return 'solution_architect'
        return False

    @api.model
    def _default_lead_type(self):
        partner_type = self._get_user_partner_type()
        if partner_type == 'channel_manager':
            return 'independent_agent'
        if partner_type == 'solution_architect':
            return 'solution_architect'
        return False

    # These fields are readonly for their own Partner Type, and Odoo does not
    # send readonly fields on save, so the #26 onchange alone would not persist
    # them. A server-side default guarantees the value on every create path.
    @api.model
    def _default_channel_manager_id(self):
        if self._get_user_partner_type() == 'channel_manager' \
                and self._is_partner_tagged(
                    self.env.user.partner_id,
                    'crm_deals.partner_category_channel_manager'):
            return self.env.user.partner_id
        return False

    @api.model
    def _default_solution_architect_ids(self):
        # An x2many default must be a list of ids/commands: returning False
        # leaves the field unusable on virtual (onchange) records.
        if self._get_user_partner_type() == 'solution_architect':
            return [Command.set(self.env.user.partner_id.ids)]
        return []

    @api.constrains('solution_architect_ids')
    def _check_solution_architect_ids(self):
        for lead in self:
            if len(lead.solution_architect_ids) > self._MAX_SOLUTION_ARCHITECTS:
                raise ValidationError(_(
                    "A lead can have at most %(max)s Solution Architects, "
                    "but %(count)s were selected.",
                    max=self._MAX_SOLUTION_ARCHITECTS,
                    count=len(lead.solution_architect_ids),
                ))

    @api.depends_context('uid')
    def _compute_user_partner_type(self):
        partner_type = self._get_user_partner_type()
        for lead in self:
            lead.user_partner_type = partner_type
            lead.is_leads_admin = partner_type == 'leads_admin'

    # Fields each Partner Type may not change once set by their group.
    _PARTNER_TYPE_LOCKED_FIELDS = {
        'channel_manager': ('lead_type', 'channel_manager_id'),
        'solution_architect': ('lead_type', 'solution_architect_ids'),
    }

    def _check_partner_type_write(self, vals):
        """Enforce the group rules outside the form too (import, API, list edit)."""
        if self.env.su:
            return
        locked = self._PARTNER_TYPE_LOCKED_FIELDS.get(self._get_user_partner_type())
        if not locked:
            return
        blocked = [f for f in locked if f in vals]
        if blocked:
            labels = ', '.join(self._fields[f].string for f in blocked)
            raise UserError(_(
                "Your Partner Type does not allow changing: %s.", labels,
            ))

    @api.model
    def _is_partner_tagged(self, partner, tag_xmlid):
        """Whether a contact carries the tag, resolved by XML id.

        Used to keep the auto-fill inside what the field's domain allows.
        An absent tag means nothing qualifies, matching
        ``_domain_partners_tagged``, which then returns an empty domain.
        """
        tag = self.env.ref(tag_xmlid, raise_if_not_found=False)
        return bool(tag) and tag in partner.category_id

    def _domain_partners_tagged(self, tag_xmlid):
        """Restrict a contact field to partners carrying the given tag.

        Resolved through the tag's XML id rather than a hardcoded database id.
        """
        tag = self.env.ref(tag_xmlid, raise_if_not_found=False)
        return [('category_id', '=', tag.id)] if tag else []

    # Values handed to a contact created from this lead. The company gets the
    # organisation-level fields; the person gets only the title. With no company
    # name there is one contact, so it takes all of them.
    _COMPANY_CONTACT_FIELDS = (
        'industry_id', 'subsector_id', 'core_line_of_business', 'location_count',
        'technology_ids',
    )
    _PERSON_CONTACT_FIELDS = ('job_title_id',)

    def _deal_contact_values(self, *field_groups):
        """Lead values for the named fields, skipping empty ones.

        Converted by the field's own type: a many2one contributes its id and a
        many2many a Command.set, since these values go straight into
        res.partner.create() / write().
        """
        self.ensure_one()
        values = {}
        for name in (name for group in field_groups for name in group):
            field = self._fields[name]
            value = self[name]
            if not value:
                continue
            if field.type == 'many2one':
                values[name] = value.id
            elif field.type in ('many2many', 'one2many'):
                values[name] = [Command.set(value.ids)]
            else:
                values[name] = value
        return values

    def _prepare_customer_values(self, partner_name, is_company=False, parent_id=False):
        """Carry the lead's company and contact fields onto the new partner.

        Extending this one method covers every creation path, since core funnels
        all of them through it: the Create Contact button, New Quotation, lead
        conversion and _get_customer_information.
        """
        values = super()._prepare_customer_values(
            partner_name, is_company=is_company, parent_id=parent_id)
        if is_company:
            values.update(self._deal_contact_values(self._COMPANY_CONTACT_FIELDS))
        elif parent_id:
            # The company beside it already took the organisation-level fields.
            values.update(self._deal_contact_values(self._PERSON_CONTACT_FIELDS))
        else:
            # A lone person contact carries everything.
            values.update(self._deal_contact_values(
                self._COMPANY_CONTACT_FIELDS, self._PERSON_CONTACT_FIELDS))
        return values

    def _handle_partner_assignment(self, force_partner_id=False, create_missing=True,
                                   with_parent=None):
        """Also top up an existing contact that is being linked.

        Only empty fields are filled; an existing value is never overwritten.
        """
        res = super()._handle_partner_assignment(
            force_partner_id=force_partner_id, create_missing=create_missing,
            with_parent=with_parent)
        if force_partner_id:
            for lead in self:
                lead._fill_missing_partner_values(lead.partner_id)
        return res

    def _fill_missing_partner_values(self, partner):
        """Fill only the fields that are still empty on this contact."""
        self.ensure_one()
        if not partner:
            return
        wanted = self._deal_contact_values(
            self._COMPANY_CONTACT_FIELDS,
            () if partner.is_company else self._PERSON_CONTACT_FIELDS,
        )
        # Every mirrored field is falsy when unset, location_count
        # included now that it is a selection, so "not set" is just falsiness.
        vals = {name: value for name, value in wanted.items()
                if not partner[name]}
        if vals:
            partner.write(vals)

    def _get_real_deal_lines(self):
        """Deal lines that carry amounts: sections and notes excluded."""
        self.ensure_one()
        return self.deal_line_ids.filtered(lambda line: not line.display_type)

    @api.depends('deal_line_ids')
    def _compute_deal_currency_id(self):
        usd = self.env.ref('base.USD')
        for lead in self:
            lead.deal_currency_id = usd

    @api.depends('deal_line_ids.estimated_monthly_cost',
                 'deal_line_ids.estimated_one_time_revenue',
                 'deal_line_ids.display_type',
                 'deal_line_ids.status')
    def _compute_deal_totals(self):
        for lead in self:
            lines = lead._get_real_deal_lines()
            lead.deal_monthly_total = sum(lines.mapped('estimated_monthly_cost'))
            lead.deal_onetime_total = sum(lines.mapped('estimated_one_time_revenue'))

    @api.depends('deal_onetime_total')
    def _compute_expected_revenue(self):
        for lead in self:
            if lead._get_real_deal_lines():
                lead.expected_revenue = lead.deal_onetime_total
            else:
                # No real deal lines: keep any manually entered value.
                lead.expected_revenue = lead.expected_revenue

    @api.depends('deal_monthly_total')
    def _compute_recurring_revenue(self):
        for lead in self:
            if lead._get_real_deal_lines():
                lead.recurring_revenue = lead.deal_monthly_total
            else:
                lead.recurring_revenue = lead.recurring_revenue

    @api.depends('deal_monthly_total')
    def _compute_recurring_plan(self):
        # Referenced by XML id so the amount reads as a monthly figure.
        monthly = self.env.ref('crm.crm_recurring_plan_monthly',
                               raise_if_not_found=False)
        for lead in self:
            if monthly and lead._get_real_deal_lines():
                lead.recurring_plan = monthly
            else:
                lead.recurring_plan = lead.recurring_plan

    @api.depends('partner_id')
    def _compute_industry_id(self):
        # Default from the customer, but stay editable afterwards.
        for lead in self:
            if lead.partner_id.industry_id:
                lead.industry_id = lead.partner_id.industry_id
            elif not lead.industry_id:
                lead.industry_id = False

    @api.depends('partner_id', 'industry_id')
    def _compute_subsector_id(self):
        for lead in self:
            subsector = lead.subsector_id
            if lead.partner_id.subsector_id:
                subsector = lead.partner_id.subsector_id
            # A sub-sector belongs to a single industry.
            if subsector.industry_id and subsector.industry_id != lead.industry_id:
                subsector = False
            lead.subsector_id = subsector

    @api.onchange('subsector_id')
    def _onchange_subsector_default_technologies(self):
        """Swap the auto-added technologies for the new sub-sector's defaults.

        Driven by the sub-sector alone - Industry carries no Default Tech Stack
        and never touches Tech Stack. Whatever the user added by hand is kept:
        only the items added automatically last time are taken out.

        Clearing the sub-sector leaves Tech Stack exactly as it is, which also
        covers an industry change clearing a mismatched sub-sector through
        _compute_subsector_id. `auto_technology_ids` is deliberately left in
        place on that path, so picking another sub-sector afterwards still
        swaps out the previous one's defaults rather than piling onto them.
        """
        for lead in self:
            if not lead.subsector_id:
                continue
            new_defaults = lead.subsector_id.default_technology_ids
            manual = lead.technology_ids - lead.auto_technology_ids
            # x2many edits inside an onchange must go through Command: a plain
            # recordset assignment does not register on the virtual record.
            lead.technology_ids = [Command.set((manual | new_defaults).ids)]
            lead.auto_technology_ids = [Command.set(new_defaults.ids)]

    @api.onchange('lead_type')
    def _onchange_lead_type(self):
        """Prefill the current user's contact on the fields that apply.

        Only fills a field that is visible for the selected lead type and is
        still empty: an invisible field is never populated and an existing
        value is never overwritten.
        """
        partner = self.env.user.partner_id
        # Never prefill a contact the field's domain would reject (#51).
        if self.lead_type == 'independent_agent' and not self.channel_manager_id \
                and self._is_partner_tagged(
                    partner, 'crm_deals.partner_category_channel_manager'):
            self.channel_manager_id = partner
        if (self.lead_type in ('referral_partner', 'solution_architect')
                and not self.solution_architect_ids):
            # x2many edits inside an onchange must go through Command: a plain
            # recordset assignment does not register on the virtual record.
            self.solution_architect_ids = [Command.set(partner.ids)]

    @api.onchange('deal_template_id')
    def _onchange_deal_template_id(self):
        """Load the template's lines, unless the lead already has deal lines.

        In that case nothing is added, replaced or removed: the user is warned
        and the template selection is reverted to its previous value.
        """
        if not self.deal_template_id:
            return
        if self.deal_line_ids:
            previous = self._origin.deal_template_id
            self.deal_template_id = previous
            return {
                'warning': {
                    'title': _("Deal Template"),
                    'message': _(
                        "Deal template not loaded \u2014 this lead already has "
                        "deal lines."
                    ),
                },
            }
        self.deal_line_ids = [
            Command.create(vals)
            for vals in self.deal_template_id._prepare_deal_line_values()
        ]
        # The template's customer-facing notes, but never over notes already
        # typed on the lead (#60).
        if is_html_empty(self.budget_note) and self.deal_template_id.budget_note:
            self.budget_note = self.deal_template_id.budget_note

    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        for lead, vals in zip(leads, vals_list):
            # The lead type picks the pipeline (#62), unless the caller named
            # a team itself - the portal, the backend, an import or the API.
            if not vals.get('team_id'):
                lead._apply_team_for_lead_type()
            # Load the template only when no lines were supplied on creation.
            if vals.get('deal_template_id') and not vals.get('deal_line_ids'):
                lead.deal_line_ids = [
                    Command.create(line_vals)
                    for line_vals in lead.deal_template_id._prepare_deal_line_values()
                ]
            # Same rule as the onchange: fill the notes only when the lead
            # carries none of its own (#60).
            if vals.get('deal_template_id') and is_html_empty(lead.budget_note) \
                    and lead.deal_template_id.budget_note:
                lead.budget_note = lead.deal_template_id.budget_note
            # Portal submissions, imports and API calls never run the onchange,
            # so the sub-sector's defaults are applied here instead. Only when
            # no Tech Stack was supplied: an explicit value given on creation is
            # never overridden. No sub-sector means no change, whatever the
            # industry is.
            # Created straight into a stage that schedules the meeting (#61).
            if lead.stage_id.schedule_budget_review:
                lead._schedule_budget_review_activity()
            if not vals.get('technology_ids') and lead.subsector_id:
                defaults = lead.subsector_id.default_technology_ids
                if defaults:
                    lead.technology_ids = [Command.set(defaults.ids)]
                    lead.auto_technology_ids = [Command.set(defaults.ids)]
        return leads

    @api.depends('deal_line_ids.task_id', 'deal_line_ids.project_id')
    def _compute_deal_work_counts(self):
        for lead in self:
            lead.deal_task_count = len(lead.deal_line_ids.task_id)
            lead.deal_project_count = len(
                lead.deal_line_ids.project_id.filtered('active')
            )

    def action_create_contact(self):
        """Open sale_crm's New Quotation customer wizard in contact-only mode.

        The wizard (crm.quotation.partner) and its create/link logic are reused
        as-is; contact_only makes its action_apply stop after assigning the
        partner instead of opening a quotation.
        """
        self.ensure_one()
        action = self.env['ir.actions.actions']._for_xml_id(
            'sale_crm.crm_quotation_partner_action')
        action['name'] = _("Create Contact")
        action['context'] = {
            'active_model': self._name,
            'active_id': self.id,
            'active_ids': self.ids,
            'contact_only': True,
        }
        return action

    def _compute_commission_count(self):
        Commission = self.env['crm.deal.commission'].sudo()
        data = Commission._read_group(
            domain=[('lead_id', 'in', self.ids)],
            groupby=['lead_id'], aggregates=['__count'])
        mapped = {lead.id: count for lead, count in data}
        for lead in self:
            lead.commission_count = mapped.get(lead.id, 0)

    def action_view_commissions(self):
        """Open the Commissions Forecast action itself, so its views, search
        view, filters and group-bys all come along.

        The lead is applied as search_default_lead_id rather than a domain, so
        the facet can be removed to reveal the full forecast.
        """
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'crm_deals.crm_deal_commission_action')
        context = action.get('context') or {}
        if isinstance(context, str):
            context = safe_eval(context, {'uid': self.env.uid})
        action['context'] = dict(context, search_default_lead_id=self.id)
        return action

    def action_view_deal_tasks(self):
        self.ensure_one()
        tasks = self.deal_line_ids.task_id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tasks'),
            'res_model': 'project.task',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', tasks.ids)],
            'context': {'default_partner_id': self.partner_id.id},
        }

    def action_view_deal_projects(self):
        self.ensure_one()
        projects = self.deal_line_ids.project_id.filtered('active')
        if len(projects) == 1:
            action = self.env['ir.actions.actions'].with_context(
                active_id=projects.id,
            )._for_xml_id('project.act_project_project_2_project_task_all')
            action['context'] = {
                'active_id': projects.id,
                'default_project_id': projects.id,
                'default_partner_id': self.partner_id.id,
            }
            return action
        return {
            'type': 'ir.actions.act_window',
            'name': _('Projects'),
            'res_model': 'project.project',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', projects.ids)],
            'context': {'default_partner_id': self.partner_id.id},
        }

    def write(self, vals):
        self._check_partner_type_write(vals)
        # Detect leads transitioning INTO a won stage: the target stage is won
        # and the lead's current (pre-write) stage is not. This excludes writes
        # made while the lead is already in a won stage.
        won_transition_leads = self.env['crm.lead']
        # Leads entering a stage flagged for the budget review meeting (#61).
        budget_review_leads = self.env['crm.lead']
        if vals.get('stage_id'):
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            if new_stage.is_won:
                won_transition_leads = self.filtered(
                    lambda lead: not lead.stage_id.is_won
                )
            if new_stage.schedule_budget_review:
                budget_review_leads = self.filtered(
                    lambda lead: lead.stage_id != new_stage)
        res = super().write(vals)

        if won_transition_leads:
            gms_company = self.env['crm.team']._gms_company()

            gms_won_leads = won_transition_leads.filtered(
                lambda lead: lead.company_id == gms_company
            )

            if gms_won_leads:
                gms_won_leads._generate_deal_projects_and_tasks()
                gms_won_leads.deal_line_ids.filtered(
                    lambda line: (
                        not line.display_type
                        and line.status == 'accepted'
                    )
                )._generate_commissions()
        for lead in budget_review_leads:
            lead._schedule_budget_review_activity()
        # A lead type change moves the lead to that type's pipeline (#62),
        # unless the same write already named a team.
        if 'lead_type' in vals and not vals.get('team_id'):
            self._apply_team_for_lead_type()
        return res

    def _generate_deal_projects_and_tasks(self):
        """Generate projects/tasks from each lead's accepted deal lines when it
        becomes won. Runs as sudo (project/task creation needs elevated rights,
        as sale_project itself does) and reports non-service lines it skipped."""
        for lead in self:
            # Only these lead types generate delivery work (#27). Independent
            # Agent, and an unset lead type, create no project or task.
            if lead.lead_type not in ('referral_partner', 'solution_architect'):
                continue
            accepted_lines = lead.deal_line_ids.filtered(
                lambda line: not line.display_type and line.status == 'accepted'
            )
            skipped = accepted_lines.sudo()._generate_projects_and_tasks()
            if skipped:
                names = ', '.join(skipped.mapped('product_id.display_name'))
                lead.message_post(body=_(
                    "The following accepted deal lines were skipped during "
                    "project/task generation because their product is not a "
                    "service: %s", names,
                ))
        return True

    def action_open_deal_line_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Deal Line',
            'res_model': 'crm.deal.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_lead_id': self.id},
        }

    # ------------------------------------------------------------------
    # Customer Budget Summary (#58)
    # ------------------------------------------------------------------
    def _compute_access_url(self):
        super()._compute_access_url()
        for lead in self:
            lead.access_url = '/my/budget/%s' % lead.id

    def _get_report_base_filename(self):
        """Filename for the portal's own report download (#58)."""
        self.ensure_one()
        return _("Budget Summary - %s", self.name or '')

    def _budget_sections(self):
        """The lead's lines grouped into section blocks, in sequence order.

        Lines before the first section - or on a lead with none - land in a
        synthetic "Other Services" block with id 0. Note lines travel inside
        their block and are rendered as plain rows.
        """
        self.ensure_one()
        blocks = []
        current = None
        for line in self.deal_line_ids.sorted(lambda l: (l.sequence, l.id)):
            if line.display_type == 'line_section':
                current = {'id': line.id, 'name': line.name or _("Services"),
                           'lines': self.env['crm.deal.line']}
                blocks.append(current)
                continue
            if current is None:
                current = {'id': 0, 'name': _("Other Services"),
                           'lines': self.env['crm.deal.line']}
                blocks.append(current)
            current['lines'] |= line
        return [block for block in blocks if block['lines']]

    def _budget_section_term(self, lines):
        """The shared contract term of a block, or "Varies"."""
        terms = set(lines.filtered(lambda l: not l.display_type).mapped('contract_term'))
        if len(terms) == 1:
            term = terms.pop()
            return dict(
                self.env['crm.deal.line']._fields['contract_term'].selection
            ).get(term, '') if term else ''
        return _("Varies")

    def _budget_data(self):
        """Everything the portal page, the PDF and the JSON refresh read."""
        self.ensure_one()
        blocks = []
        for block in self._budget_sections():
            reals = block['lines'].filtered(lambda l: not l.display_type)
            accepted = reals.filtered(lambda l: l.status == 'accepted')
            blocks.append(dict(
                block,
                monthly=sum(accepted.mapped('estimated_monthly_cost')),
                onetime=sum(accepted.mapped('estimated_one_time_revenue')),
                term=self._budget_section_term(reals),
            ))
        reals = self._get_real_deal_lines()
        accepted = reals.filtered(lambda l: l.status == 'accepted')
        return {
            'blocks': blocks,
            'monthly': sum(accepted.mapped('estimated_monthly_cost')),
            'onetime': sum(accepted.mapped('estimated_one_time_revenue')),
            'proposed_monthly': sum(reals.mapped('estimated_monthly_cost')),
            'proposed_onetime': sum(reals.mapped('estimated_one_time_revenue')),
            'all_decided': bool(reals) and all(
                line.status in ('accepted', 'rejected') for line in reals),
            'is_signed': bool(self.budget_signed_on),
        }

    def budget_format_amount(self, amount):
        """One currency formatter for the page, the PDF and the JSON refresh."""
        self.ensure_one()
        return formatLang(self.env, amount or 0.0,
                          currency_obj=self.deal_currency_id)

    def _budget_live_values(self):
        """Figures that move when the customer accepts or rejects a service,
        keyed by the `data-budget-field` the page carries."""
        self.ensure_one()
        data = self._budget_data()
        values = {
            'total_monthly': self.budget_format_amount(data['monthly']),
            'total_onetime': self.budget_format_amount(data['onetime']),
        }
        for block in data['blocks']:
            values['section_%s_monthly' % block['id']] = \
                self.budget_format_amount(block['monthly'])
            values['section_%s_onetime' % block['id']] = \
                self.budget_format_amount(block['onetime'])
        return values

    def _check_budget_ready(self):
        """Refuse to send a budget the customer could not act on."""
        self.ensure_one()
        if not self.partner_id or not self.partner_id.email:
            raise UserError(_(
                "Set a customer with an email first (use Create Contact)."))
        lines = self._get_real_deal_lines()
        if not lines:
            raise UserError(_(
                "This opportunity has no services to send. Add deal lines "
                "first."))
        # The same validation the Accept button runs, so the customer never
        # meets a validation error on the portal.
        lines._check_ready_to_accept()

    def action_send_budget_summary(self):
        """Open the mail composer on the Budget Summary template."""
        if len(self) != 1:
            raise UserError(_(
                "Select a single opportunity to send its Budget Summary."))
        self._check_budget_ready()
        self._portal_ensure_token()
        template = self.env.ref(
            'crm_deals.mail_template_budget_summary', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'name': _("Send Budget Summary"),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_model': 'crm.lead',
                'default_res_ids': self.ids,
                'default_template_id': template.id if template else False,
                'default_composition_mode': 'comment',
                'default_email_layout_xmlid': 'mail.mail_notification_layout',
                'force_email': True,
                # Read back by message_post to stamp the send date.
                'mark_budget_as_sent': True,
            },
        }

    def action_preview_budget_summary(self):
        """Open the customer's own page, token and all, in a new tab."""
        self.ensure_one()
        self._portal_ensure_token()
        return {
            'type': 'ir.actions.act_url',
            'url': self.get_portal_url(),
            'target': 'new',
        }

    def action_reset_budget_signature(self):
        """Leads Administrator only: unlock the budget so it can be re-sent."""
        for lead in self:
            # Skipped under sudo, like _check_partner_type_write, so
            # server-side code and migrations are not locked out.
            if not self.env.su and not lead.is_leads_admin:
                raise UserError(_(
                    "Only a Leads Administrator can reset a budget signature."))
            tag = self.env.ref('crm_deals.crm_tag_budget_signed',
                               raise_if_not_found=False)
            vals = {
                'budget_signature': False,
                'budget_signed_by': False,
                'budget_signed_on': False,
            }
            if tag and tag in lead.tag_ids:
                vals['tag_ids'] = [Command.unlink(tag.id)]
            lead.write(vals)
            lead.message_post(body=_("Budget signature reset; the budget can "
                                     "be revised and sent again."))
        return True

    def _budget_apply_signature(self, name, signature):
        """Store the customer's signature, tag the lead and file the PDF.

        Called from the portal controller, which has already validated the
        token and that every service has been decided.
        """
        self.ensure_one()
        self.write({
            'budget_signed_by': name,
            'budget_signed_on': fields.Datetime.now(),
            'budget_signature': signature,
        })
        tag = self.env.ref('crm_deals.crm_tag_budget_signed',
                           raise_if_not_found=False)
        if tag and tag not in self.tag_ids:
            self.write({'tag_ids': [Command.link(tag.id)]})
        # Flush first: the report renders in its own cursor and must see the
        # signature that was just written.
        self.env.flush_all()
        pdf, _dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'crm_deals.action_report_budget_summary', self.ids)
        self.message_post(
            body=_("Budget Summary signed by %s.", name),
            attachments=[('Budget Summary - %s.pdf' % (self.name or ''), pdf)],
            author_id=self.partner_id.id or None,
        )
        # The customer's signature is the only trigger for contract
        # preparation work (#60) - no stage change and no backend acceptance.
        self._create_contract_prep_activities()
        return True

    def _team_for_lead_type(self, lead_type):
        """The pipeline a lead type belongs to (#62), by XML id.

        Independent Agent deals run in Agent Channel; Referral Partner and
        Solution Architect deals run in Solutions.
        """
        Team = self.env['crm.team']
        if lead_type == 'independent_agent':
            return Team._gms_agent_channel_team() or Team
        if lead_type in ('referral_partner', 'solution_architect'):
            return Team._gms_solutions_team() or Team
        return Team

    def _apply_team_for_lead_type(self):
        """Move each lead to its type's team, keeping a shared stage (#62).

        A stage with empty `team_ids` belongs to every pipeline and is kept;
        anything else is replaced by the new team's first stage by sequence,
        which is what Odoo's own stage compute would pick.
        """
        gms_company = self.env['crm.team']._gms_company()

        for lead in self:
            if lead.company_id != gms_company:
                continue

            team = lead._team_for_lead_type(lead.lead_type)
            if not team or lead.team_id == team:
                continue
            values = {'team_id': team.id}
            stage = lead.stage_id
            if stage and stage.team_ids and team not in stage.team_ids:
                new_stage = self.env['crm.stage'].search(
                    ['|', ('team_ids', '=', False), ('team_ids', 'in', team.ids)],
                    order='sequence, id', limit=1)
                if new_stage:
                    values['stage_id'] = new_stage.id
            lead.write(values)
        return True

    def _get_budget_assignee(self):
        """Who owns the budget work on this lead (#60, #61).

        Exactly one Solution Architect whose contact has an active internal
        user wins; no SA, several of them, or an SA with no user falls back to
        the lead's salesperson. One helper for both the contract-prep
        activities and the budget review meeting, so the rule cannot drift.
        """
        self.ensure_one()
        if len(self.solution_architect_ids) == 1:
            users = self.solution_architect_ids.sudo().user_ids.filtered(
                lambda user: user.active and user._is_internal())
            if users:
                return users[0]
        return self.user_id

    def _schedule_budget_review_activity(self):
        """One Budget Review Meeting activity per lead reaching the flagged
        stage (#61). Skipped when an open one is already there."""
        self.ensure_one()
        activity_type = self.env.ref(
            'crm_deals.mail_activity_type_budget_review',
            raise_if_not_found=False)
        if not activity_type:
            return False
        existing = self.sudo().activity_ids.filtered(
            lambda activity: activity.activity_type_id == activity_type)
        if existing:
            return False
        user = self._get_budget_assignee()
        if not user:
            self.message_post(body=_(
                "Budget review meeting could not be scheduled: no Solution "
                "Architect or Salesperson is set."))
            return False
        data = self._budget_data()
        customer = (self.partner_id.display_name or self.partner_name
                    or self.name or '')
        contact = (self.partner_id.name or self.contact_name or customer)
        note = _(
            "The budget for %(lead)s is ready. Schedule a meeting with "
            "%(contact)s to review it.",
            lead=self.name or '', contact=contact)
        figures = _(
            "Proposed: %(monthly)s monthly / %(onetime)s one-time across "
            "%(count)s services.",
            monthly=self.budget_format_amount(data['proposed_monthly']),
            onetime=self.budget_format_amount(data['proposed_onetime']),
            count=len(self._get_real_deal_lines()))
        self.sudo().activity_schedule(
            act_type_xmlid='crm_deals.mail_activity_type_budget_review',
            date_deadline=activity_type._get_date_deadline(),
            summary=_("Set budget review meeting with %s", customer),
            note='<p>%s</p><p>%s</p>' % (note, figures),
            user_id=user.id,
        )
        return True

    def _create_contract_prep_activities(self):
        """One Prepare Contracts activity per accepted service (#60).

        On the **lead**, so it reaches the pipeline card and the activity
        menu, and never twice for the same line - `contract_prep_requested`
        records which services have had theirs.
        """
        self.ensure_one()
        lines = self.deal_line_ids.filtered(
            lambda line: not line.display_type and line.status == 'accepted'
            and not line.contract_prep_requested)
        if not lines:
            return False
        user = self._get_budget_assignee()
        if not user:
            self.message_post(body=_(
                "Contract preparation activities could not be created: no "
                "Solution Architect or Salesperson is set."))
            return False
        lead = self.sudo()
        # activity_schedule() defaults the deadline to today: the type's delay
        # is applied by an onchange, which never runs on create. Ask the type
        # for its own date instead, so the 3 days configured on it hold.
        activity_type = self.env.ref(
            'crm_deals.mail_activity_type_prepare_contracts',
            raise_if_not_found=False)
        deadline = activity_type._get_date_deadline() if activity_type else None
        for line in lines:
            lead.activity_schedule(
                act_type_xmlid='crm_deals.mail_activity_type_prepare_contracts',
                date_deadline=deadline,
                summary=line._contract_prep_summary(),
                note=line._contract_prep_note(),
                user_id=user.id,
            )
            line.sudo().contract_prep_requested = True
        self.message_post(body=_(
            "Contract preparation activities created for %(count)s services, "
            "assigned to %(user)s.", count=len(lines), user=user.name))
        return True

    def message_post(self, **kwargs):
        """Stamp the send date when the composer sends the Budget Summary.

        The recipients are also subscribed, which is one of the ways the
        portal lets a signed-in customer back in when their link has been
        mislaid (#58 fix).
        """
        if self.env.context.get('mark_budget_as_sent'):
            self.sudo().write({'budget_sent_date': fields.Datetime.now()})
            recipients = {pid for pid in (kwargs.get('partner_ids') or [])
                          if isinstance(pid, int)}
            if self.partner_id:
                recipients.add(self.partner_id.id)
            if recipients:
                self.sudo().message_subscribe(partner_ids=list(recipients))
        return super().message_post(**kwargs)

    def action_hand_off_to_gms(self):
        """Turn an Independent Agent deal into a GMS referral (#62).

        The agent becomes the referral partner - that is who gets paid - while
        the Channel Manager and Independent Agent stay on record. Runs sudo so
        the Partner Type locks (`_check_partner_type_write`) do not block it,
        and the Solution Architect is left for a human to choose.
        """
        gms_company = self.env['crm.team']._gms_company()

        for lead in self:
            if lead.company_id != gms_company:
                raise UserError(_(
                    "Only GMS opportunities can be handed off."
                ))

            if lead.lead_type != 'independent_agent':
                raise UserError(_(
                    "Only an Independent Agent deal can be handed off to GMS."))
            if not (lead.is_leads_admin
                    or lead.user_partner_type == 'channel_manager'
                    or self.env.su):
                raise UserError(_(
                    "Only a Channel Manager or a Leads Administrator can hand "
                    "a deal off to GMS."))
            solutions = self.env['crm.team']._gms_solutions_team()
            warm = self.env.ref('crm_deals.stage_new_warm',
                                raise_if_not_found=False)
            values = {
                'lead_type': 'referral_partner',
                # The agent is compensated as the referral partner now.
                'referral_partner_id': lead.independent_agent_id.id,
            }
            if not solutions or solutions.company_id != gms_company:
                raise UserError(_(
                    "The GMS Solutions team is not configured correctly."
                ))

            if not warm or solutions not in warm.team_ids:
                raise UserError(_(
                    "The GMS New - Warm stage is not configured correctly."
                ))

            values['team_id'] = solutions.id
            values['stage_id'] = warm.id

            lead.sudo().write(values)
            # Someone has to pick the Solution Architect by hand.
            manager = lead.channel_manager_id.sudo().user_ids.filtered(
                lambda user: user.active and user._is_internal())
            assignee = manager[:1] or lead.user_id
            if assignee:
                lead.sudo().activity_schedule(
                    'mail.mail_activity_data_todo',
                    date_deadline=fields.Date.context_today(lead)
                    + relativedelta(days=1),
                    summary=_("Assign Solution Architect"),
                    note=_("Choose a Solution Architect for %s.",
                           lead.name or ''),
                    user_id=assignee.id,
                )
            lead.message_post(body=_(
                "Handed off to GMS by %s: now a Referral Partner deal in the "
                "Solutions pipeline.", self.env.user.name))
        return True

    def action_accept_all_deals(self):
        draft_lines = self.deal_line_ids.filtered(
            lambda l: not l.display_type and l.status == 'draft')
        draft_lines.write({'status': 'accepted'})

    def action_reject_all_deals(self):
        draft_lines = self.deal_line_ids.filtered(
            lambda l: not l.display_type and l.status == 'draft')
        draft_lines.write({'status': 'rejected'})
