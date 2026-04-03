from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    x_gms_primary_solution_category_id = fields.Many2one(
        "product.product", string="Primary Solution Category"
    )
    x_gms_expected_monthly_volume = fields.Float(string="Expected Monthly Volume")
    x_gms_expected_contract_term = fields.Integer(string="Expected Contract Term (Months)")
    x_gms_primary_rep_id = fields.Many2one("res.partner", string="Primary Rep")
    x_gms_support_manager_id = fields.Many2one("res.partner", string="Support Manager")
    x_gms_channel_manager_id = fields.Many2one("res.partner", string="Channel Manager")

    gms_proposal_ids = fields.One2many(
        "gms.client.proposal", "crm_lead_id", string="Proposals"
    )
    x_gms_proposal_count = fields.Integer(
        string="Proposal Count", compute="_compute_gms_proposal_stats"
    )
    x_gms_latest_proposal_id = fields.Many2one(
        "gms.client.proposal", string="Latest Proposal", compute="_compute_gms_proposal_stats"
    )

    @api.depends("gms_proposal_ids")
    def _compute_gms_proposal_stats(self):
        for rec in self:
            rec.x_gms_proposal_count = len(rec.gms_proposal_ids)
            rec.x_gms_latest_proposal_id = rec.gms_proposal_ids[:1].id if rec.gms_proposal_ids else False
