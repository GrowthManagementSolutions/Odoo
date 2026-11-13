from markupsafe import Markup

from odoo import _, api, fields, models


class ConfigDocument(models.Model):
    _name = 'config.document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Configuration Document'
    _order = 'id desc'

    reference = fields.Char(
        string='Config Document ID',
        readonly=True,
        copy=False,
        index=True,
    )
    name = fields.Char(
        string='Document Name',
        compute='_compute_name',
        store=True,
        readonly=True,
    )
    document_type_id = fields.Many2one(
        'config.document.type',
        string='Document Type',
        required=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Company',
        required=True,
        domain=[('is_company', '=', True)],
        tracking=True,
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
        ],
        string='Status',
        default='pending',
        required=True,
        tracking=True,
    )
    owner_id = fields.Many2one(
        'res.users',
        string='Owner',
        default=lambda self: self.env.user,
        tracking=True,
    )
    note = fields.Html(string='Note')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'config_document_attachment_rel',
        'document_id',
        'attachment_id',
        string='Attachments',
    )
    unique_identifier = fields.Char(string='Unique Identifier')

    deal_line_id = fields.Many2one(
        'crm.deal.line',
        string='Deal',
        tracking=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product/Service',
        domain=[('type', '=', 'service')],
        compute='_compute_from_deal_line',
        store=True,
        readonly=False,
        tracking=True,
    )
    task_id = fields.Many2one(
        'project.task',
        string='Deployment',
        tracking=True,
    )
    # project.task records completion in `date_end`: project's write() calls
    # update_date_end(), which stamps now() when the target stage is folded and
    # clears it otherwise. There is no separate "closed on" date field.
    install_completion_date = fields.Datetime(
        string='Install Completion Date',
        related='task_id.date_end',
        readonly=True,
    )
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        compute='_compute_from_deal_line',
        store=True,
        readonly=False,
        tracking=True,
    )
    master_supplier_id = fields.Many2one(
        'res.partner',
        string='Master Supplier',
        compute='_compute_from_deal_line',
        store=True,
        readonly=False,
        tracking=True,
    )
    ticket_id = fields.Many2one(
        'helpdesk.ticket',
        string='Ticket',
        tracking=True,
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.ref('base.USD'),
    )
    # Mirrors the type so the form can show one section and hide the rest.
    detail_section = fields.Selection(
        related='document_type_id.detail_section',
        string='Detail Section',
        readonly=True,
    )

    # --- A. Telecom -------------------------------------------------------
    telecom_record_type = fields.Selection(
        selection=[
            ('call_queue', 'Call Queue/Hunt Group/Call Routing Group or Number'),
            ('voicemail', 'Voicemail Only Mailbox'),
            ('auto_attendant', 'Automated Attendant/Welcome Menu'),
            ('admin', 'GMS Admin Record'),
            ('toll_free', 'Toll-free Configuration'),
            ('virtual_license', 'Virtual License, Hardware, etc.'),
        ],
        string='Record Type',
    )
    # Call Queue/Hunt Group/Call Routing Group or Number
    hunt_group_extensions = fields.Text(string='Hunt Group Extensions')
    group_extension_or_did = fields.Char(string='Group Extension or DID')
    terminate_phone_call_queue = fields.Char(string='Terminate Phone (Call Queue)')
    # Voicemail Only Mailbox
    voicemail_extension = fields.Char(string='Extension (Voicemail)')
    voicemail_did = fields.Char(string='DID (Voicemail)')
    voicemail_pin = fields.Char(string='VM PIN (Voicemail)', groups='project.group_project_manager')
    voicemail_recipient_email = fields.Char(string='Recipient Email')
    # Automated Attendant/Welcome Menu
    auto_attendant_options = fields.Text(string='Options')
    auto_attendant_extension_or_did = fields.Char(string='Extension or DID (Automated Attendant)')
    # GMS Admin Record
    telecom_username = fields.Char(string='Username (Telecom)')
    telecom_password = fields.Char(string='Password (Telecom)', groups='project.group_project_manager')
    telecom_support_number = fields.Char(string='Support Number (Telecom)')
    admin_record_extension = fields.Char(string='Extension (Admin Record)')
    admin_user_email = fields.Char(string='User Email Address')
    telecom_account_number = fields.Char(string='Account Number (Telecom)')
    telecom_portal_website = fields.Char(string='Portal Website (Telecom)')
    # Virtual License, Hardware, etc.
    terminal_type_ids = fields.Many2many(
        'config.terminal.type',
        'config_document_terminal_type_rel',
        'document_id',
        'terminal_type_id',
        string='Terminal Type',
    )
    virtual_license_did = fields.Char(string='DID (Virtual License)')
    mailbox = fields.Boolean(string='Mailbox')
    end_email_address = fields.Char(string='End Email Address')
    virtual_license_extension = fields.Char(string='Extension (Virtual License)')
    telecom_deployment_location = fields.Char(string='Deployment Location (Telecom)')

    # --- B. Internet/Data -------------------------------------------------
    connection_type = fields.Selection(
        selection=[
            ('primary', 'Primary Connection'),
            ('backup', 'Backup Connection'),
        ],
        string='Connection Type',
    )
    equipment_ownership = fields.Selection(
        selection=[
            ('rented_by_client', 'Rented by Client'),
            ('owned_by_client', 'Owned by Client'),
            ('provided_by_supplier', 'Provided by Supplier'),
        ],
        string='Equipment Ownership',
    )
    sla = fields.Integer(string='SLA')
    internet_account_number = fields.Char(string='Account Number (Internet/Data)')
    internet_pin = fields.Char(string='PIN (Internet/Data)', groups='project.group_project_manager')
    equipment_make_model = fields.Char(string='Equipment Make Model')
    internet_connection_type = fields.Selection(
        selection=[
            ('best_effort_fiber', 'Best Effort Fiber'),
            ('dedicated_fiber', 'Dedicated Fiber'),
            ('cable', 'Cable'),
            ('dsl', 'DSL'),
            ('fixed_wireless', 'Fixed Wireless'),
            ('5g_lte', '5G/LTE'),
        ],
        string='Internet Connection Type',
    )
    static_ip_count = fields.Integer(string='No. of Static IP Addresses')
    speed_ordered = fields.Char(string='Speed Ordered')
    installation_date = fields.Date(string='Installation Date')
    equipment_admin_login = fields.Char(
        string='Equipment Admin Login', groups='project.group_project_manager')
    internet_contact_id = fields.Many2one(
        'res.partner',
        string='Contact for Internet Access',
    )

    # --- C. Payment processing -------------------------------------------
    merchant_id = fields.Char(string='Merchant ID')
    on_site_access_pin = fields.Char(
        string='PIN Code for On Site Access', groups='project.group_project_manager')
    pci_compliance_data = fields.Text(string='PCI Compliance Data')
    avg_monthly_volume = fields.Monetary(
        string='Average Monthly Processing Volume', currency_field='currency_id')
    avg_transaction_count = fields.Integer(string='Average Number of Transactions')
    pricing_model = fields.Selection(
        selection=[
            ('interchange_plus', 'Interchange Plus'),
            ('flat_rate', 'Flat Rate'),
            ('tiered', 'Tiered'),
            ('cash_discount', 'Cash Discount/Surcharge'),
        ],
        string='Pricing Model',
    )
    swipe_fee = fields.Monetary(string='Swipe Fee', currency_field='currency_id')
    basis_points = fields.Integer(string='Basis Points')
    average_ticket = fields.Monetary(string='Average Ticket', currency_field='currency_id')

    # Selectable contacts for the Internet/Data section: the company and the
    # contacts underneath it.
    allowed_contact_ids = fields.Many2many(
        'res.partner',
        compute='_compute_allowed_records',
        string='Selectable Contacts',
    )

    # Selectable records are narrowed to the chosen company. Computed instead of
    # expressed as a view domain because `child_of` cannot be written with the
    # `=?` guard, and an unguarded leaf would match everything while the company
    # is still empty.
    allowed_deal_line_ids = fields.Many2many(
        'crm.deal.line',
        compute='_compute_allowed_records',
        string='Selectable Deals',
    )
    allowed_task_ids = fields.Many2many(
        'project.task',
        compute='_compute_allowed_records',
        string='Selectable Deployments',
    )
    allowed_ticket_ids = fields.Many2many(
        'helpdesk.ticket',
        compute='_compute_allowed_records',
        string='Selectable Tickets',
    )

    @api.depends('reference', 'document_type_id', 'partner_id')
    def _compute_name(self):
        for document in self:
            document.name = ' - '.join(part for part in (
                document.reference,
                document.document_type_id.name,
                document.partner_id.display_name,
            ) if part)

    @api.depends('deal_line_id')
    def _compute_from_deal_line(self):
        """Seed product and suppliers from the deal; all three stay editable."""
        for document in self:
            deal = document.deal_line_id
            document.product_id = deal.product_id
            document.supplier_id = deal.supplier_id
            document.master_supplier_id = deal.master_supplier_id

    @api.depends('partner_id')
    def _compute_allowed_records(self):
        for document in self:
            company = document.partner_id.commercial_partner_id or document.partner_id
            deal_domain = [('status', '=', 'accepted'), ('display_type', '=', False)]
            if company:
                deal_domain.append(('partner_id', 'child_of', company.id))
                document.allowed_task_ids = self.env['project.task'].search(
                    [('partner_id', 'child_of', company.id)])
                document.allowed_ticket_ids = self.env['helpdesk.ticket'].search(
                    [('partner_id', 'child_of', company.id)])
                document.allowed_contact_ids = self.env['res.partner'].search(
                    [('id', 'child_of', company.id)])
            else:
                document.allowed_task_ids = self.env['project.task']
                document.allowed_ticket_ids = self.env['helpdesk.ticket']
                document.allowed_contact_ids = self.env['res.partner']
            document.allowed_deal_line_ids = self.env['crm.deal.line'].search(deal_domain)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference') or vals['reference'] == '/':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'config.document') or '/'
        documents = super().create(vals_list)
        documents._sync_attachments()
        for document in documents:
            document._post_attachment_change(document.attachment_ids.mapped('name'), [])
        return documents

    def write(self, vals):
        # Names are captured up front: the many2many_binary widget sends unlink
        # commands, so removed attachments no longer exist after super().
        snapshots = {}
        if 'attachment_ids' in vals:
            snapshots = {
                document.id: {a.id: a.name for a in document.attachment_ids}
                for document in self
            }
        res = super().write(vals)
        if 'attachment_ids' in vals:
            self._sync_attachments()
            for document in self:
                before = snapshots.get(document.id, {})
                after = {a.id: a.name for a in document.attachment_ids}
                document._post_attachment_change(
                    [name for att_id, name in after.items() if att_id not in before],
                    [name for att_id, name in before.items() if att_id not in after],
                )
        return res

    def _sync_attachments(self):
        """Own the linked attachments so they surface in the chatter and are
        dropped together with the document."""
        for document in self:
            stray = document.attachment_ids.filtered(
                lambda a: a.res_model != document._name or a.res_id != document.id)
            if stray:
                stray.write({'res_model': document._name, 'res_id': document.id})

    def _post_attachment_change(self, added, removed):
        self.ensure_one()
        parts = []
        if added:
            parts.append(_('Files added: %s', ', '.join(added)))
        if removed:
            parts.append(_('Files removed: %s', ', '.join(removed)))
        if parts:
            self.message_post(body=Markup('<br/>').join(parts))

    @api.model
    def _prefill_action(self, defaults):
        """Open a blank document in a dialog, pre-filled from the source record."""
        context = dict(self.env.context)
        context.update({'default_%s' % key: value for key, value in defaults.items()})
        return {
            'type': 'ir.actions.act_window',
            'name': _('New Configuration Document'),
            'res_model': 'config.document',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': context,
        }
