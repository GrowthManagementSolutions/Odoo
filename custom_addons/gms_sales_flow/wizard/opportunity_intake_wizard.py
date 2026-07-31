from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GmsOpportunityIntakeWizard(models.TransientModel):
    _name = "gms.opportunity.intake.wizard"
    _description = "GMS New Opportunity Intake"

    company_name = fields.Char(
        string="Company Name",
        required=True,
    )

    

    street = fields.Char(string="Street")
    street2 = fields.Char(string="Street 2")
    city = fields.Char(string="City")
    state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="State",
    )
    zip = fields.Char(string="ZIP")
    country_id = fields.Many2one(
        comodel_name="res.country",
        string="Country",
        default=lambda self: self.env.company.country_id,
    )

    contact_name = fields.Char(
        string="Contact",
        required=True,
    )

    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")

    channel_involved = fields.Boolean(
        string="Channel Involved?",
    )

    has_referral_partner = fields.Boolean(
        string="Referral Partner Involved?",
    )

    referral_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Referral Partner",
    )

    independent_agent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Independent Agent",
    )

    salesperson_id = fields.Many2one(
        comodel_name="res.users",
        string="Salesperson",
        required=True,
        default=lambda self: self.env.user,
        domain="[('share', '=', False)]",
    )

    @api.onchange("channel_involved")
    def _onchange_channel_involved(self):
        for wizard in self:
            if wizard.channel_involved:
                wizard.has_referral_partner = False
                wizard.referral_partner_id = False
            else:
                wizard.independent_agent_id = False

    @api.onchange("has_referral_partner")
    def _onchange_has_referral_partner(self):
        for wizard in self:
            if not wizard.has_referral_partner:
                wizard.referral_partner_id = False

    @api.constrains("phone", "email")
    def _check_phone_or_email(self):
        for wizard in self:
            if not wizard.phone and not wizard.email:
                raise ValidationError(
                    _("Enter at least a phone number or an email address.")
                )

    @api.constrains(
        "channel_involved",
        "has_referral_partner",
        "referral_partner_id",
        "independent_agent_id",
    )
    def _check_partner_requirements(self):
        for wizard in self:
            if (
                not wizard.channel_involved
                and wizard.has_referral_partner
                and not wizard.referral_partner_id
            ):
                raise ValidationError(
                    _("Select a Referral Partner.")
                )

            if (
                wizard.channel_involved
                and not wizard.independent_agent_id
            ):
                raise ValidationError(
                    _("Select an Independent Agent.")
                )

    def _get_sales_team(self):
        self.ensure_one()

        team_name = (
            "GMS Sales - Channel"
            if self.channel_involved
            else "GMS Sales"
        )

        team = self.env["crm.team"].search(
            [
                ("name", "=", team_name),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

        if not team:
            raise ValidationError(
                _("Sales Team '%s' was not found.") % team_name
            )

        return team

    def action_create_opportunity(self):
        self.ensure_one()

        team = self._get_sales_team()

        values = {
            "name": self.company_name.strip(),
            "type": "opportunity",
            "partner_name": self.company_name.strip(),
            "contact_name": self.contact_name.strip(),
            "phone": self.phone,
            "email_from": self.email,
            "street": self.street,
            "street2": self.street2,
            "city": self.city,
            "state_id": self.state_id.id,
            "zip": self.zip,
            "country_id": self.country_id.id,
            "user_id": self.salesperson_id.id,
            "team_id": team.id,
            
            "gms_sales_channel": (
                "channel"
                if self.channel_involved
                else "direct"
            ),
            "gms_referral_partner_id": self.referral_partner_id.id,
            "gms_independent_agent_id": self.independent_agent_id.id,
        }

        lead = self.env["crm.lead"].create(values)

        return {
            "type": "ir.actions.act_window",
            "name": _("Opportunity"),
            "res_model": "crm.lead",
            "view_mode": "form",
            "res_id": lead.id,
            "target": "current",
        }