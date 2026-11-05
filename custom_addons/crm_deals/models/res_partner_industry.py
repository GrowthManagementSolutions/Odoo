from odoo import fields, models


class ResPartnerIndustry(models.Model):
    _inherit = 'res.partner.industry'

    subsector_ids = fields.One2many(
        'res.partner.subsector',
        'industry_id',
        string='Sub-sectors',
    )
