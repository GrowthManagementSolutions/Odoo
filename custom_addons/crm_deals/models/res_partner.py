from odoo import _, api, fields, models

# No. of Locations, shared verbatim by res.partner and crm.lead so the two
# cannot drift. Labels match the values; empty means "not stated".
LOCATION_COUNT_SELECTION = [
    (str(number), str(number)) for number in range(1, 21)
] + [('20+', '20+')]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    deal_line_count = fields.Integer(
        string='Deals Count',
        compute='_compute_deal_line_count',
    )
    subsector_id = fields.Many2one(
        'res.partner.subsector',
        string='Sub-sector',
        domain="[('industry_id', '=', industry_id)]",
    )
    master_agreement_ids = fields.One2many(
        'product.master.agreement',
        'master_id',
        string='Master Agreements',
    )
    master_agreement_count = fields.Integer(
        compute='_compute_master_agreement_count')
    # Drive the view's visibility off the tags rather than repeating a
    # category_id expression in every arch.
    is_supplier_tagged = fields.Boolean(compute='_compute_partner_tagged')
    is_master_supplier_tagged = fields.Boolean(compute='_compute_partner_tagged')
    is_referral_partner_tagged = fields.Boolean(compute='_compute_partner_tagged')
    is_independent_agent_tagged = fields.Boolean(compute='_compute_partner_tagged')
    # Who normally works this partner's deals (#61). Read through
    # _get_default_budget_contact(), which falls back to the commercial
    # partner, so a company configured once covers all its people.
    default_solution_architect_id = fields.Many2one(
        'res.partner',
        string='Default Solution Architect',
        domain=lambda self: self._domain_tagged(
            'crm_deals.partner_category_solution_architect'),
    )
    default_channel_manager_id = fields.Many2one(
        'res.partner',
        string='Default Channel Manager',
        domain=lambda self: self._domain_tagged(
            'crm_deals.partner_category_channel_manager'),
    )
    # Which way a contact carrying both tags submits by default (#62).
    default_partner_role = fields.Selection(
        selection=[
            ('referral_partner', 'Referral Partner'),
            ('independent_agent', 'Independent Agent'),
        ],
        string='Default Partner Role',
        help="How this partner submits leads from the portal when they are "
             "both a Referral Partner and an Independent Agent. Empty means "
             "Referral Partner.",
    )
    location_count = fields.Selection(
        selection=LOCATION_COUNT_SELECTION,
        string='No. of Locations',
    )
    primary_partner_id = fields.Many2one('res.partner', string='Primary')
    secondary_partner_id = fields.Many2one('res.partner', string='Secondary')
    referral_partner_id = fields.Many2one('res.partner', string='Referral Partner')
    district_manager_id = fields.Many2one('res.partner', string='District Manager')
    regional_manager_id = fields.Many2one('res.partner', string='Regional Manager')
    w9_legal_business_name = fields.Char(string='W9 Legal Business Name')
    dba = fields.Char(string='DBA')
    business_type = fields.Selection(
        selection=[
            ('llc_llp', 'LLC/LLP'),
            ('sole_proprietorship', 'Sole Proprietorship'),
            ('private_corp', 'Private Corporation (S-Corp or C-Corp)'),
            ('non_profit', 'Non-Profit'),
            ('public_corp', 'Public Corporation'),
            ('partnership', 'Partnership'),
            ('government', 'Government'),
            ('other', 'Other'),
        ],
        string='Business Type',
    )
    company_status = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('closed', 'Closed'),
        ],
        string='Company Status',
    )
    business_established_date = fields.Date(string='Business Established Date')
    main_technical_contact_id = fields.Many2one(
        'res.partner',
        string='Main Technical/IT Contact',
    )
    core_line_of_business = fields.Char(string='Core Line of Business')
    technology_ids = fields.Many2many('res.partner.technology', string='Tech Stack')
    job_title_id = fields.Many2one('res.partner.job.title', string='Title')
    personal_email = fields.Char(string='Personal Email')
    personal_phone = fields.Char(string='Personal Phone')
    scheduling_link = fields.Char(string='Scheduling Link')
    birthday = fields.Date(string='Birthday')
    ownership_percentage = fields.Float(string='Ownership Percentage')

    @api.onchange('industry_id')
    def _onchange_industry_id_clear_subsector(self):
        # A sub-sector belongs to a single industry; drop it when the industry
        # changes so a stale sub-sector can't survive an industry switch.
        if self.subsector_id.industry_id != self.industry_id:
            self.subsector_id = False

    def _compute_deal_line_count(self):
        data = self.env['crm.deal.line']._read_group(
            domain=[
                ('partner_id', 'in', self.ids),
                ('display_type', '=', False),
                ('status', '!=', 'draft'),
            ],
            groupby=['partner_id'],
            aggregates=['__count'],
        )
        mapped = {partner.id: count for partner, count in data}
        for partner in self:
            partner.deal_line_count = mapped.get(partner.id, 0)

    def action_view_deal_lines(self):
        self.ensure_one()
        return {
            'name': 'Deals',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.deal.line',
            'view_mode': 'kanban,list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('display_type', '=', False),
                ('status', '!=', 'draft'),
            ],
            'context': {'search_default_group_by_lead': 1},
        }

    # --- Configuration documents (#43) ---
    config_document_count = fields.Integer(
        string='Config Documents',
        compute='_compute_config_document_count',
    )

    def _compute_config_document_count(self):
        for partner in self:
            company = partner.commercial_partner_id or partner
            partner.config_document_count = self.env['config.document'].search_count(
                [('partner_id', 'child_of', company.id)])

    def action_view_config_documents(self):
        self.ensure_one()
        company = self.commercial_partner_id or self
        return {
            'name': _('Config Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'config.document',
            'view_mode': 'list,kanban,form',
            'domain': [('partner_id', 'child_of', company.id)],
            'context': {'default_partner_id': company.id},
        }

    @api.model
    def _domain_tagged(self, tag_xmlid):
        """Restrict a contact field to partners carrying the given tag.

        The single source for the Supplier / Master Supplier domains used by
        the route models, resolved through the tag's XML id rather than a
        hardcoded database id. An absent tag matches nothing, which is the
        same convention crm.lead._domain_partners_tagged follows.
        """
        tag = self.env.ref(tag_xmlid, raise_if_not_found=False)
        return [('category_id', '=', tag.id)] if tag else []

    @api.depends('category_id')
    def _compute_partner_tagged(self):
        supplier = self.env.ref(
            'crm_deals.partner_category_supplier', raise_if_not_found=False)
        master = self.env.ref(
            'crm_deals.partner_category_master_supplier',
            raise_if_not_found=False)
        referral = self.env.ref(
            'crm_deals.partner_category_referral_partner',
            raise_if_not_found=False)
        agent = self.env.ref(
            'crm_deals.partner_category_independent_agent',
            raise_if_not_found=False)
        for partner in self:
            partner.is_supplier_tagged = bool(
                supplier) and supplier in partner.category_id
            partner.is_master_supplier_tagged = bool(
                master) and master in partner.category_id
            partner.is_referral_partner_tagged = bool(
                referral) and referral in partner.category_id
            partner.is_independent_agent_tagged = bool(
                agent) and agent in partner.category_id

    def _get_default_budget_contact(self, field_name):
        """The contact's own default SA / CM, else its company's (#61)."""
        self.ensure_one()
        partner = self.sudo()
        return partner[field_name] or partner.commercial_partner_id[field_name]

    @api.depends('master_agreement_ids')
    def _compute_master_agreement_count(self):
        data = self.env['product.master.agreement']._read_group(
            domain=[('master_id', 'in', self.ids)],
            groupby=['master_id'], aggregates=['__count'])
        mapped = {partner.id: count for partner, count in data}
        for partner in self:
            partner.master_agreement_count = mapped.get(partner.id, 0)

    def action_view_master_agreements(self):
        self.ensure_one()
        return {
            'name': _('Master Agreements'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.master.agreement',
            'view_mode': 'list,form',
            'domain': [('master_id', '=', self.id)],
            'context': {'default_master_id': self.id},
        }

    def _get_gms_share(self, date=None):
        """GMS's share under the agreement effective on ``date``, else False.

        False and 0.0 are different answers: False means this master supplier
        has no agreement covering that date at all, which the route form
        surfaces as a warning rather than silently treating as nothing.
        """
        self.ensure_one()
        date = date or fields.Date.context_today(self)
        agreement = self.env['product.master.agreement'].search([
            ('master_id', '=', self.id),
            '|', ('date_from', '=', False), ('date_from', '<=', date),
            '|', ('date_to', '=', False), ('date_to', '>=', date),
        ], order='date_from desc', limit=1)
        return agreement.gms_share if agreement else False