from odoo import models, fields


class ProjectProject(models.Model):
    _inherit = "project.project"

    gms_project_type = fields.Selection([
        ("accounts_payable", "Accounts Payable"),
        ("accounts_receivable", "Accounts Receivable"),
        ("client_request", "Client Request"),
        ("commissions", "Commissions"),
        ("event_management", "Event Management"),
        ("independent_agent_portal", "Independent Agent Portal"),
        ("internal_portal", "Internal Portal"),
        ("it_support", "IT Support"),
        ("marketing", "Marketing"),
        ("miscellaneous", "Miscellaneous"),
        ("operations_portal", "Operations Portal"),
        ("ops_maint", "Ops/Maint"),
        ("referral_partner_portal", "Referral Partner Portal"),
        ("servis_ai", "Servis.ai"),
        ("webinar", "Webinar"),
    ], string="Project Type")

    gms_project_manager_id = fields.Many2one(
        "res.users",
        string="Project Manager",
        default=lambda self: self.env.user,
    )

    gms_assigned_user_ids = fields.Many2many(
        "res.users",
        "project_gms_assigned_users_rel",
        "project_id",
        "user_id",
        string="Assigned People",
    )

    gms_priority = fields.Selection([
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ], string="Priority", default="medium")

    gms_due_date = fields.Date(string="Due Date")

    gms_remarks = fields.Text(string="Remarks")

    gms_url = fields.Char(string="URL")

    gms_attachment_ids = fields.Many2many(
        "ir.attachment",
        "project_gms_attachment_rel",
        "project_id",
        "attachment_id",
        string="Attachments",
    )

    # References

    gms_account_id = fields.Many2one(
        "account.account",
        string="Account",
    )

    gms_applicant_id = fields.Many2one(
        "hr.applicant",
        string="Applicant",
    )

    gms_commission_id = fields.Many2one(
        "gms.commission.earning",
        string="Commission",
    )

    gms_company_id = fields.Many2one(
        "res.company",
        string="Company",
    )

    gms_configuration_document_id = fields.Many2one(
        "ir.attachment",
        string="Configuration Document",
    )

    gms_contact_id = fields.Many2one(
        "res.partner",
        string="Contact",
    )

    gms_deal_id = fields.Many2one(
        "crm.lead",
        string="Deal",
    )

    gms_deployment_id = fields.Many2one(
        "project.project",
        string="Deployment",
    )

    gms_lead_id = fields.Many2one(
        "crm.lead",
        string="Lead",
    )

    gms_user_id = fields.Many2one(
        "res.users",
        string="User",
    )

    gms_task_id = fields.Many2one(
        "project.task",
        string="Task",
    )

    # Output

    gms_output_file_ids = fields.Many2many(
        "ir.attachment",
        "project_gms_output_attachment_rel",
        "project_id",
        "attachment_id",
        string="Output Files",
    )

    gms_link_output = fields.Char(
        string="Link Output",
    )

    gms_text_output = fields.Text(
        string="Text Output",
    )