from odoo import api, fields, models, _


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # ============================================================
    # WEEK 1 - GMS FOUNDATION
    # ============================================================

    gms_is_gms_record = fields.Boolean(
        string="GMS Sales Record",
        default=False,
        tracking=True,
        index=True,
        help=(
            "Enable when the lead or opportunity uses the "
            "GMS sales workflow."
        ),
    )

    gms_sales_channel = fields.Selection(
        selection=[
            ("direct", "Direct"),
            ("channel", "Channel"),
        ],
        string="GMS Sales Channel",
        tracking=True,
        index=True,
    )

    gms_lead_status = fields.Selection(
        selection=[
            ("new", "New"),
            ("attempting", "Attempting to Connect"),
            ("gatekeeper", "Stuck at Gatekeeper"),
            (
                "connected_followup",
                "Connected - Follow-Up Needed",
            ),
            (
                "connected_appointment",
                "Connected - Appointment Set",
            ),
            ("qualified", "Qualified"),
            ("disqualified", "Disqualified"),
            ("do_not_call", "Do Not Call"),
            ("bad_contact", "Bad Contact Information"),
        ],
        string="GMS Lead Status",
        default="new",
        tracking=True,
        index=True,
    )

    gms_lead_source = fields.Selection(
        selection=[
            ("manual", "Manual Entry"),
            ("website", "Website"),
            ("referral_partner", "Referral Partner"),
            ("independent_agent", "Independent Agent"),
            ("supplier", "Supplier"),
            ("import", "Imported"),
            ("other", "Other"),
        ],
        string="GMS Lead Source",
        tracking=True,
        index=True,
    )

    gms_intake_notification_sent = fields.Boolean(
        string="Intake Notification Sent",
        default=False,
        copy=False,
        readonly=True,
    )

    # ============================================================
    # WEEK 2 - CLASSIFICATION / CHANNEL / DEAL FOUNDATION
    # ============================================================

    gms_industry_id = fields.Many2one(
        comodel_name="gms.solution.category",
        string="Industry",
        tracking=True,
        domain="[('parent_id', '=', False)]",
    )

    gms_industry_subset_id = fields.Many2one(
        comodel_name="gms.solution.category",
        string="Industry Subset",
        tracking=True,
        domain="[('parent_id', '=', gms_industry_id)]",
    )

    gms_channel_type = fields.Selection(
        selection=[
            ("referral_partner", "Referral Partner"),
            ("independent_agent", "Independent Agent"),
        ],
        string="Channel Type",
        tracking=True,
    )

    gms_referral_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Referral Partner",
        tracking=True,
    )

    gms_independent_agent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Independent Agent",
        tracking=True,
    )

    gms_closed_lost_reason_id = fields.Many2one(
        comodel_name="gms.closed.lost.reason",
        string="Closed Lost Reason",
        tracking=True,
    )

    gms_closed_lost_notes = fields.Text(
        string="Closed Lost Notes",
        tracking=True,
    )

    # ============================================================
    # ONCHANGE LOGIC
    # ============================================================

    @api.onchange("gms_sales_channel")
    def _onchange_gms_sales_channel(self):
        direct_team = self.env.ref(
            "gms_sales_flow.gms_crm_team_direct",
            raise_if_not_found=False,
        )

        channel_team = self.env.ref(
            "gms_sales_flow.gms_crm_team_channel",
            raise_if_not_found=False,
        )

        for lead in self:
            if lead.gms_sales_channel == "direct":
                if direct_team:
                    lead.team_id = direct_team

                lead.gms_channel_type = False
                lead.gms_referral_partner_id = False
                lead.gms_independent_agent_id = False

            elif lead.gms_sales_channel == "channel":
                if channel_team:
                    lead.team_id = channel_team

    @api.onchange("gms_channel_type")
    def _onchange_gms_channel_type(self):
        for lead in self:
            if lead.gms_channel_type == "referral_partner":
                lead.gms_independent_agent_id = False

            elif lead.gms_channel_type == "independent_agent":
                lead.gms_referral_partner_id = False

            else:
                lead.gms_referral_partner_id = False
                lead.gms_independent_agent_id = False

    @api.onchange("gms_industry_id")
    def _onchange_gms_industry_id(self):
        for lead in self:
            if (
                lead.gms_industry_subset_id
                and lead.gms_industry_subset_id.parent_id
                != lead.gms_industry_id
            ):
                lead.gms_industry_subset_id = False

    # ============================================================
    # VALIDATIONS
    # ============================================================

    @api.constrains(
        "gms_is_gms_record",
        "gms_sales_channel",
        "gms_channel_type",
        "gms_referral_partner_id",
        "gms_independent_agent_id",
    )
    def _check_gms_channel_configuration(self):
        for lead in self:
            if not lead.gms_is_gms_record:
                continue

            if lead.gms_sales_channel == "direct":
                if (
                    lead.gms_channel_type
                    or lead.gms_referral_partner_id
                    or lead.gms_independent_agent_id
                ):
                    raise models.ValidationError(
                        _(
                            "Direct GMS opportunities cannot have "
                            "a Referral Partner or Independent Agent."
                        )
                    )

            if lead.gms_sales_channel == "channel":
                if not lead.gms_channel_type:
                    raise models.ValidationError(
                        _("Select a Channel Type.")
                    )

                if (
                    lead.gms_channel_type == "referral_partner"
                    and not lead.gms_referral_partner_id
                ):
                    raise models.ValidationError(
                        _("Select a Referral Partner.")
                    )

                if (
                    lead.gms_channel_type == "independent_agent"
                    and not lead.gms_independent_agent_id
                ):
                    raise models.ValidationError(
                        _("Select an Independent Agent.")
                    )

    @api.constrains(
        "gms_industry_id",
        "gms_industry_subset_id",
    )
    def _check_gms_industry_subset(self):
        for lead in self:
            if (
                lead.gms_industry_subset_id
                and lead.gms_industry_subset_id.parent_id
                != lead.gms_industry_id
            ):
                raise models.ValidationError(
                    _(
                        "The selected Industry Subset must belong "
                        "to the selected Industry."
                    )
                )

    # ============================================================
    # ROUTING
    # ============================================================

    def _get_gms_target_team(self):
        self.ensure_one()

        if self.gms_sales_channel == "direct":
            return self.env.ref(
                "gms_sales_flow.gms_crm_team_direct",
                raise_if_not_found=False,
            )

        if self.gms_sales_channel == "channel":
            return self.env.ref(
                "gms_sales_flow.gms_crm_team_channel",
                raise_if_not_found=False,
            )

        return self.env["crm.team"]

    def _apply_gms_team_routing(self):
        for lead in self:
            if not lead.gms_is_gms_record:
                continue

            target_team = lead._get_gms_target_team()

            if target_team and lead.team_id != target_team:
                super(CrmLead, lead).write(
                    {
                        "team_id": target_team.id,
                    }
                )

    # ============================================================
    # NOTIFICATIONS
    # ============================================================

    def _gms_get_notification_user(self):
        self.ensure_one()

        team = self.team_id or self._get_gms_target_team()

        if team and team.user_id:
            return team.user_id

        group_xml_id = (
            "gms_sales_flow.group_gms_solution_architect"
            if self.gms_sales_channel == "direct"
            else "gms_sales_flow.group_gms_channel_manager"
        )

        group = self.env.ref(
            group_xml_id,
            raise_if_not_found=False,
        )

        if group:
            users = group.user_ids.filtered(
                lambda user: (
                    user.active
                    and self.company_id in user.company_ids
                )
            )

            if users:
                return users[0]

        if self.user_id:
            return self.user_id

        return self.env.user

    def _gms_create_intake_notification(self):
        activity_type = self.env.ref(
            "mail.mail_activity_data_todo",
            raise_if_not_found=False,
        )

        for lead in self:
            if (
                not lead.gms_is_gms_record
                or lead.gms_intake_notification_sent
                or not activity_type
            ):
                continue

            target_user = lead._gms_get_notification_user()

            if not target_user:
                continue

            channel_label = dict(
                lead._fields["gms_sales_channel"].selection
            ).get(
                lead.gms_sales_channel,
                lead.gms_sales_channel,
            )

            source_label = dict(
                lead._fields["gms_lead_source"].selection
            ).get(
                lead.gms_lead_source,
                lead.gms_lead_source,
            )

            note = _(
                "A new GMS lead was submitted.\n\n"
                "Company: %(company)s\n"
                "Contact: %(contact)s\n"
                "Channel: %(channel)s\n"
                "Source: %(source)s",
                company=lead.partner_name or lead.name,
                contact=lead.contact_name or _("Not provided"),
                channel=channel_label or _("Not provided"),
                source=source_label or _("Not provided"),
            )

            self.env["mail.activity"].create(
                {
                    "activity_type_id": activity_type.id,
                    "res_model_id": self.env[
                        "ir.model"
                    ]._get_id("crm.lead"),
                    "res_id": lead.id,
                    "user_id": target_user.id,
                    "summary": _("Review new GMS lead"),
                    "note": note,
                    "date_deadline": fields.Date.context_today(
                        lead
                    ),
                }
            )

            lead.message_post(
                body=_(
                    "New GMS webform submission routed to "
                    "%(team)s. Review activity assigned to "
                    "%(user)s.",
                    team=lead.team_id.display_name,
                    user=target_user.display_name,
                )
            )

            super(CrmLead, lead).write(
                {
                    "gms_intake_notification_sent": True,
                }
            )

    # ============================================================
    # CREATE / WRITE
    # ============================================================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        records._apply_gms_team_routing()

        webform_records = records.filtered(
            lambda lead: (
                lead.gms_is_gms_record
                and lead.gms_lead_source
                in {
                    "website",
                    "referral_partner",
                    "independent_agent",
                    "supplier",
                    "other",
                }
            )
        )

        webform_records._gms_create_intake_notification()

        return records

    def write(self, vals):
        result = super().write(vals)

        if {
            "gms_is_gms_record",
            "gms_sales_channel",
        }.intersection(vals):
            self._apply_gms_team_routing()

        return result