import logging

from odoo import _, fields, http
from odoo.http import request


_logger = logging.getLogger(__name__)


class GMSLeadWebformController(http.Controller):

    @http.route(
        "/gms/lead/direct",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
        sitemap=True,
    )
    def gms_direct_lead_form(self, **kwargs):
        return request.render(
            "gms_sales_flow.gms_direct_lead_form_template",
            {
                "error": kwargs.get("error"),
                "values": {},
            },
        )

    @http.route(
        "/gms/lead/channel",
        type="http",
        auth="public",
        website=True,
        methods=["GET"],
        sitemap=True,
    )
    def gms_channel_lead_form(self, **kwargs):
        return request.render(
            "gms_sales_flow.gms_channel_lead_form_template",
            {
                "error": kwargs.get("error"),
                "values": {},
            },
        )

    @http.route(
        "/gms/lead/direct/submit",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def gms_direct_lead_submit(self, **post):
        return self._create_gms_lead(
            post=post,
            sales_channel="direct",
            lead_source="website",
            success_template=(
                "gms_sales_flow.gms_direct_lead_success_template"
            ),
            form_template=(
                "gms_sales_flow.gms_direct_lead_form_template"
            ),
        )

    @http.route(
        "/gms/lead/channel/submit",
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def gms_channel_lead_submit(self, **post):
        source = post.get("lead_source") or "independent_agent"

        allowed_sources = {
            "referral_partner",
            "independent_agent",
            "supplier",
            "other",
        }

        if source not in allowed_sources:
            source = "other"

        return self._create_gms_lead(
            post=post,
            sales_channel="channel",
            lead_source=source,
            success_template=(
                "gms_sales_flow.gms_channel_lead_success_template"
            ),
            form_template=(
                "gms_sales_flow.gms_channel_lead_form_template"
            ),
        )

    def _create_gms_lead(
        self,
        post,
        sales_channel,
        lead_source,
        success_template,
        form_template,
    ):
        company_name = self._clean_text(post.get("company_name"))
        contact_name = self._clean_text(post.get("contact_name"))
        email = self._clean_text(post.get("email"))
        phone = self._clean_text(post.get("phone"))
        description = self._clean_text(post.get("description"))

        error = self._validate_submission(
            company_name=company_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
        )

        if error:
            return request.render(
                form_template,
                {
                    "error": error,
                    "values": post,
                },
            )

        website = request.website
        company = website.company_id or request.env.company

        team = self._get_target_team(sales_channel)

        stage = request.env.ref(
            "gms_sales_flow.gms_stage_lead_received",
            raise_if_not_found=False,
        )

        lead_name = company_name

        if contact_name:
            lead_name = f"{company_name} - {contact_name}"

        lead_values = {
            "name": lead_name,
            "partner_name": company_name,
            "contact_name": contact_name,
            "email_from": email,
            "phone": phone,
            "description": description,
            "company_id": company.id,
            "gms_is_gms_record": True,
            "gms_sales_channel": sales_channel,
            "gms_lead_status": "new",
            "gms_lead_source": lead_source,
        }

        if team:
            lead_values["team_id"] = team.id

        if stage:
            lead_values["stage_id"] = stage.id

        try:
            lead = (
                request.env["crm.lead"]
                .sudo()
                .with_company(company)
                .create(lead_values)
            )

            lead._gms_create_intake_notification()

        except Exception:
            _logger.exception(
                "Unable to create GMS lead from public webform."
            )

            return request.render(
                form_template,
                {
                    "error": _(
                        "We could not submit your request. "
                        "Please try again or contact GMS directly."
                    ),
                    "values": post,
                },
            )

        return request.render(
            success_template,
            {
                "lead": lead,
            },
        )

    def _get_target_team(self, sales_channel):
        xml_id = (
            "gms_sales_flow.gms_crm_team_direct"
            if sales_channel == "direct"
            else "gms_sales_flow.gms_crm_team_channel"
        )

        return request.env.ref(
            xml_id,
            raise_if_not_found=False,
        )

    @staticmethod
    def _validate_submission(
        company_name,
        contact_name,
        email,
        phone,
    ):
        if not company_name:
            return _("Company Name is required.")

        if not contact_name:
            return _("Contact Name is required.")

        if not email and not phone:
            return _(
                "Enter at least one contact method: Email or Phone."
            )

        if email and "@" not in email:
            return _("Enter a valid email address.")

        return False

    @staticmethod
    def _clean_text(value):
        if not value:
            return False

        return str(value).strip()[:5000]