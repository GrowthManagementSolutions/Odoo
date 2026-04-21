from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class GmsClientProposal(models.Model):
    _name = "gms.client.proposal"
    _description = "GMS Client Proposal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "proposal_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(required=True, copy=False, readonly=True, default="New")
    crm_lead_id = fields.Many2one("crm.lead", tracking=True, ondelete="restrict")
    partner_id = fields.Many2one("res.partner", required=True, tracking=True, ondelete="restrict")

    assigned_rep_id = fields.Many2one(
        "res.users",
        string="Assigned Rep",
        required=True,
        tracking=True,
        default=lambda self: self.env.user,
        ondelete="restrict",
    )

    support_manager_id = fields.Many2one("res.partner")
    channel_manager_id = fields.Many2one("res.partner")

    parent_proposal_id = fields.Many2one("gms.client.proposal", copy=False, ondelete="set null")
    revision_ids = fields.One2many("gms.client.proposal", "parent_proposal_id")
    revision_number = fields.Integer(default=1, required=True)
    is_current_revision = fields.Boolean(default=True, tracking=True)

    state = fields.Selection([
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("pending_review", "Pending Review"),
        ("ready_to_send", "Ready to Send"),
        ("sent", "Sent"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("superseded", "Superseded"),
        ("expired_revision_needed", "Expired - Needs Revision"),
    ], default="draft", required=True, tracking=True)

    proposal_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    valid_until = fields.Date(required=True, tracking=True)
    sent_date = fields.Date()
    accepted_date = fields.Date()
    expired_date = fields.Date()

    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )

    merchant_ids = fields.One2many("gms.client.proposal.merchant", "proposal_id", copy=True)
    line_ids = fields.One2many("gms.client.proposal.line", "proposal_id", copy=True)
    section_ids = fields.One2many("gms.client.proposal.section", "proposal_id", copy=True)
    ack_item_ids = fields.One2many("gms.client.proposal.ack_item", "proposal_id", copy=True)
    review_ids = fields.One2many("gms.proposal.review", "proposal_id", copy=False)

    requires_review = fields.Boolean(
        compute="_compute_requires_review",
        store=True,
        tracking=True,
    )
    review_reason_summary = fields.Text(
        compute="_compute_review_reason_summary",
        store=True,
    )
    manual_review_requested = fields.Boolean(default=False, tracking=True)

    total_monthly_recurring = fields.Monetary(
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_one_time_fees = fields.Monetary(
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    total_contract_value = fields.Monetary(
        compute="_compute_totals",
        store=True,
        currency_field="currency_id",
    )
    contract_term_summary = fields.Char(
        compute="_compute_contract_term_summary",
        store=True,
    )

    template_id = fields.Many2one("gms.sow.template", ondelete="restrict")
    document_intro = fields.Html()
    document_summary = fields.Html()
    document_assumptions = fields.Html()
    document_exclusions = fields.Html()
    acceptance_block_text = fields.Html()

    ack_section_required = fields.Boolean(compute="_compute_ack_section_required", store=True)
    acknowledgment_initials_required = fields.Boolean(default=True)

    generated_pdf_attachment_id = fields.Many2one("ir.attachment", copy=False)
    generated_pdf_name = fields.Char()

    accepted_locked = fields.Boolean(default=False, tracking=True)
    converted_to_customer = fields.Boolean(default=False, copy=False)
    converted_on = fields.Datetime(copy=False)
    converted_by = fields.Many2one("res.users", copy=False)

    notes_internal = fields.Text()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        required=True,
    )

    _sql_constraints = [
        ("proposal_name_unique", "unique(name, company_id)", "Proposal number must be unique per company."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = seq.next_by_code("gms.client.proposal") or "New"

            if not vals.get("assigned_rep_id"):
                vals["assigned_rep_id"] = self.env.user.id

        return super().create(vals_list)

    @api.onchange("crm_lead_id")
    def _onchange_crm_lead(self):
        if not self.crm_lead_id:
            return

        self.partner_id = self.crm_lead_id.partner_id
        self.assigned_rep_id = self.crm_lead_id.user_id or self.env.user
        self.support_manager_id = self.crm_lead_id.x_gms_support_manager_id
        self.channel_manager_id = self.crm_lead_id.x_gms_channel_manager_id

    @api.onchange("template_id")
    def _onchange_template(self):
        if not self.template_id:
            return

        self.document_intro = self.template_id.default_intro
        self.document_summary = self.template_id.default_scope
        self.document_assumptions = self.template_id.default_assumptions
        self.document_exclusions = self.template_id.default_exclusions
        self.acceptance_block_text = self.template_id.acceptance_block_text

        self.section_ids = [(5, 0, 0)]
        sections = []
        for sec in self.template_id.section_ids:
            sections.append((0, 0, {
                "section_code": sec.section_code,
                "title": sec.title,
                "body_html": sec.default_text,
                "included": True,
                "editable": sec.editable,
                "sort_order": sec.sort_order,
            }))
        self.section_ids = sections

    @api.depends(
        "line_ids.monthly_recurring_fee",
        "line_ids.one_time_fee",
        "line_ids.line_contract_value",
    )
    def _compute_totals(self):
        for rec in self:
            rec.total_monthly_recurring = sum(rec.line_ids.mapped("monthly_recurring_fee"))
            rec.total_one_time_fees = sum(rec.line_ids.mapped("one_time_fee"))
            rec.total_contract_value = sum(rec.line_ids.mapped("line_contract_value"))

    @api.depends("line_ids.contract_term_months")
    def _compute_contract_term_summary(self):
        for rec in self:
            terms = sorted(set(rec.line_ids.mapped("contract_term_months")))
            rec.contract_term_summary = ", ".join(str(t) for t in terms if t) if terms else False

    @api.depends("line_ids.requires_review", "manual_review_requested")
    def _compute_requires_review(self):
        for rec in self:
            rec.requires_review = rec.manual_review_requested or any(rec.line_ids.mapped("requires_review"))

    @api.depends("line_ids.review_reason", "manual_review_requested")
    def _compute_review_reason_summary(self):
        for rec in self:
            reasons = [r for r in rec.line_ids.mapped("review_reason") if r]
            if rec.manual_review_requested:
                reasons.append(_("Manual review requested by rep"))
            rec.review_reason_summary = "\n".join(reasons) if reasons else False

    @api.depends("ack_item_ids.resolved", "ack_item_ids.active")
    def _compute_ack_section_required(self):
        for rec in self:
            rec.ack_section_required = any(item.active and not item.resolved for item in rec.ack_item_ids)

    @api.constrains("valid_until", "proposal_date")
    def _check_dates(self):
        for rec in self:
            if rec.valid_until and rec.proposal_date and rec.valid_until < rec.proposal_date:
                raise ValidationError(_("Valid Until cannot be before Proposal Date."))

    def action_set_in_progress(self):
        self.write({"state": "in_progress"})

    def action_request_review(self):
        for rec in self:
            rec.manual_review_requested = True
            rec.state = "pending_review"

    def action_mark_ready_to_send(self):
        for rec in self:
            if rec.requires_review:
                raise UserError(_("Proposal requires review before it can be marked Ready to Send."))
            rec.state = "ready_to_send"

    def action_mark_sent(self):
        self.write({"state": "sent", "sent_date": fields.Date.context_today(self)})

    def action_mark_accepted(self):
        for rec in self:
            if rec.state not in ("ready_to_send", "sent"):
                raise UserError(_("Only sent or ready proposals can be accepted."))
            rec.write({
                "state": "accepted",
                "accepted_date": fields.Date.context_today(self),
                "accepted_locked": True,
            })

    def action_mark_rejected(self):
        self.write({"state": "rejected"})

    def action_clone_revision(self):
        self.ensure_one()
        new_vals = self.copy_data()[0]
        new_vals.update({
            "parent_proposal_id": self.id,
            "revision_number": self.revision_number + 1,
            "is_current_revision": True,
            "state": "draft",
            "accepted_locked": False,
            "generated_pdf_attachment_id": False,
            "generated_pdf_name": False,
            "sent_date": False,
            "accepted_date": False,
            "expired_date": False,
            "converted_to_customer": False,
            "converted_on": False,
            "converted_by": False,
            "assigned_rep_id": self.assigned_rep_id.id or self.env.user.id,
        })
        self.write({"is_current_revision": False, "state": "superseded"})
        new_proposal = self.create(new_vals)
        for item in self.ack_item_ids.filtered(lambda i: i.carryforward and not i.resolved):
            item.copy({"proposal_id": new_proposal.id, "source_revision_id": self.id})
        return {
            "type": "ir.actions.act_window",
            "res_model": "gms.client.proposal",
            "view_mode": "form",
            "res_id": new_proposal.id,
        }

    @api.model
    def cron_expire_proposals(self):
        today = fields.Date.today()
        proposals = self.search([
            ("state", "in", ["draft", "in_progress", "pending_review", "ready_to_send", "sent"]),
            ("valid_until", "<", today),
        ])
        proposals.write({
            "state": "expired_revision_needed",
            "expired_date": today,
        })