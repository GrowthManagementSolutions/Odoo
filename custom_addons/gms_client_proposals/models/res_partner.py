from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    x_gms_partner_type = fields.Selection([
        ("prospect", "Prospect"),
        ("customer", "Customer"),
        ("supplier", "Supplier"),
        ("direct_rep", "Direct Rep"),
        ("referral_partner", "Referral Partner"),
        ("independent_agent", "Independent Agent"),
        ("channel_manager", "Channel Manager"),
        ("support_manager", "Support Manager"),
        ("other", "Other"),
    ], string="GMS Partner Type", tracking=True)

    x_gms_is_client = fields.Boolean(string="Is Client")
    x_gms_is_supplier = fields.Boolean(string="Is Supplier")
    x_gms_is_commission_recipient = fields.Boolean(string="Is Commission Recipient")

    x_gms_primary_rep_id = fields.Many2one("res.partner", string="Primary Rep")
    x_gms_support_manager_id = fields.Many2one("res.partner", string="Support Manager")
    x_gms_channel_manager_id = fields.Many2one("res.partner", string="Channel Manager")

    x_gms_active_for_proposals = fields.Boolean(string="Active for Proposals", default=True)

    gms_opportunity_ids = fields.One2many(
        "crm.lead",
        "partner_id",
        string="Opportunities",
    )

    gms_opportunity_count = fields.Integer(
        string="Opportunity Count",
        compute="_compute_gms_opportunity_count",
    )

    def _compute_gms_opportunity_count(self):
        for rec in self:
            rec.gms_opportunity_count = len(rec.gms_opportunity_ids)

    def action_open_gms_opportunities(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Opportunities",
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
                "default_contact_name": self.name,
            },
        }

    def action_create_gms_opportunity(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "New Opportunity",
            "res_model": "crm.lead",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_type": "opportunity",
                "default_partner_id": self.id,
                "default_name": f"{self.name} Opportunity",
                "default_x_gms_primary_rep_id": self.x_gms_primary_rep_id.id,
                "default_x_gms_support_manager_id": self.x_gms_support_manager_id.id,
                "default_x_gms_channel_manager_id": self.x_gms_channel_manager_id.id,
            },
        }

    def action_create_gms_proposal(self):
        self.ensure_one()

        opportunity = self.env["crm.lead"].search(
            [("partner_id", "=", self.id), ("type", "=", "opportunity")],
            order="create_date desc",
            limit=1,
        )

        if not opportunity:
            opportunity = self.env["crm.lead"].create({
                "name": f"{self.name} Opportunity",
                "type": "opportunity",
                "partner_id": self.id,
                "x_gms_primary_rep_id": self.x_gms_primary_rep_id.id,
                "x_gms_support_manager_id": self.x_gms_support_manager_id.id,
                "x_gms_channel_manager_id": self.x_gms_channel_manager_id.id,
            })

        rep_user = False

        if self.x_gms_primary_rep_id and self.x_gms_primary_rep_id.user_ids:
            rep_user = self.x_gms_primary_rep_id.user_ids[:1]

        if not rep_user and opportunity.user_id:
            rep_user = opportunity.user_id

        if not rep_user:
            rep_user = self.env.user

        proposal = self.env["gms.client.proposal"].create({
            "crm_lead_id": opportunity.id,
            "partner_id": self.id,
            "assigned_rep_id": rep_user.id,
            "support_manager_id": self.x_gms_support_manager_id.id or False,
            "channel_manager_id": self.x_gms_channel_manager_id.id or False,
            "valid_until": fields.Date.today() + timedelta(days=30),
        })

        return {
            "type": "ir.actions.act_window",
            "name": "Proposal",
            "res_model": "gms.client.proposal",
            "view_mode": "form",
            "res_id": proposal.id,
            "target": "current",
        }