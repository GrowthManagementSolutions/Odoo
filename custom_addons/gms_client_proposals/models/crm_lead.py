from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    # Existing GMS Proposal fields
    x_gms_primary_solution_category_id = fields.Many2one(
        "product.product",
        string="Primary Solution Category",
    )

    x_gms_expected_monthly_volume = fields.Float(
        string="Expected Monthly Volume",
    )

    x_gms_expected_contract_term = fields.Integer(
        string="Expected Contract Term (Months)",
    )

    x_gms_primary_rep_id = fields.Many2one(
        "res.partner",
        string="Primary Rep",
    )

    x_gms_support_manager_id = fields.Many2one(
        "res.partner",
        string="Support Manager",
    )

    x_gms_channel_manager_id = fields.Many2one(
        "res.partner",
        string="Channel Manager",
    )

    gms_proposal_ids = fields.One2many(
        "gms.client.proposal",
        "crm_lead_id",
        string="Proposals",
    )

    x_gms_proposal_count = fields.Integer(
        string="Proposal Count",
        compute="_compute_gms_proposal_stats",
    )

    x_gms_latest_proposal_id = fields.Many2one(
        "gms.client.proposal",
        string="Latest Proposal",
        compute="_compute_gms_proposal_stats",
    )

    # GMS Deal - Deal section
    x_gms_deal_name = fields.Char(
        string="Deal Name",
    )

    x_gms_deal_unique_identifier = fields.Char(
        string="Unique Identifier",
    )

    x_gms_company_id = fields.Many2one(
        "res.partner",
        string="Deal Company",
    )

    x_gms_deal_stage_id = fields.Many2one(
        "crm.stage",
        string="Deal Stage",
        default=lambda self: self.env["crm.stage"].search(
            [],
            order="sequence, id",
            limit=1,
        ),
    )

    x_gms_federal_tax_id = fields.Char(
        string="Federal Tax ID",
    )

    x_gms_attachment = fields.Binary(
        string="Attachment",
    )

    x_gms_attachment_filename = fields.Char(
        string="Attachment Filename",
    )

    # GMS Deal - Category section
    x_gms_service_category_id = fields.Many2one(
        "product.category",
        string="First Layer Service",
    )

    # GMS Deal - Supplier section
    x_gms_supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        domain=[("x_gms_is_supplier", "=", True)],
    )

    x_gms_master_supplier_id = fields.Many2one(
        "res.partner",
        string="Master Supplier",
        domain=[("x_gms_is_supplier", "=", True)],
    )

    x_gms_contract_term = fields.Selection(
        [
            ("month_to_month", "Month-to-Month"),
            ("12", "12 Months"),
            ("24", "24 Months"),
            ("36", "36 Months"),
            ("48", "48 Months"),
            ("60", "60 Months"),
        ],
        string="Contract Term",
        default="12",
    )

    x_gms_estimated_monthly_cost = fields.Monetary(
        string="Estimated Monthly Cost",
        currency_field="company_currency",
    )

    x_gms_estimated_one_time_revenue = fields.Monetary(
        string="Estimated One-Time Revenue",
        currency_field="company_currency",
    )

    # GMS Deal - Agent & Partner section
    x_gms_primary_agent_id = fields.Many2one(
        "res.partner",
        string="Primary",
        domain=[("x_gms_is_commission_recipient", "=", True)],
    )

    x_gms_primary_commission_rate = fields.Float(
        string="Primary Commission",
    )

    x_gms_secondary_agent_id = fields.Many2one(
        "res.partner",
        string="Secondary",
        domain=[("x_gms_is_commission_recipient", "=", True)],
    )

    x_gms_referral_partner_id = fields.Many2one(
        "res.partner",
        string="Referral Partner",
        domain=[("x_gms_is_commission_recipient", "=", True)],
    )

    x_gms_regional_manager_id = fields.Many2one(
        "res.partner",
        string="Regional Manager",
        domain=[("x_gms_is_commission_recipient", "=", True)],
    )

    x_gms_regional_manager_override_rate = fields.Float(
        string="Regional Manager Override",
    )

    x_gms_deal_notes = fields.Text(
        string="GMS Deal Notes",
    )

    @api.depends("gms_proposal_ids")
    def _compute_gms_proposal_stats(self):
        for rec in self:
            rec.x_gms_proposal_count = len(rec.gms_proposal_ids)
            rec.x_gms_latest_proposal_id = (
                rec.gms_proposal_ids[:1].id if rec.gms_proposal_ids else False
            )

    @api.onchange("partner_id")
    def _onchange_partner_id_gms_deal(self):
        for rec in self:
            if rec.partner_id:
                rec.x_gms_company_id = rec.partner_id
                rec.contact_name = rec.partner_id.name
                rec.x_gms_deal_name = f"{rec.partner_id.name} Opportunity"
                rec.x_gms_federal_tax_id = rec.partner_id.vat or False