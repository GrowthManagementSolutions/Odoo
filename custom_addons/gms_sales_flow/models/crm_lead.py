from odoo import api, fields, models, _


class CrmLead(models.Model):
    _inherit = "crm.lead"

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
            if lead.gms_sales_channel == "direct" and direct_team:
                lead.team_id = direct_team

            elif lead.gms_sales_channel == "channel" and channel_team:
                lead.team_id = channel_team

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
                    "date_deadline": fields.Date.context_today(lead),
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