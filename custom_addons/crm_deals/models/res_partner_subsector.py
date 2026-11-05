from odoo import fields, models


class ResPartnerSubsector(models.Model):
    _name = 'res.partner.subsector'
    _description = 'Partner Sub-sector'

    name = fields.Char(string='Name', required=True)
    industry_id = fields.Many2one(
        'res.partner.industry',
        string='Industry',
        required=True,
        ondelete='cascade',
    )
    # Applied to a lead's Tech Stack when this sub-sector is selected. A
    # dedicated relation table, so it cannot collide with the Tech Stack
    # relations on res.partner or crm.lead.
    default_technology_ids = fields.Many2many(
        'res.partner.technology',
        relation='res_partner_subsector_default_technology_rel',
        column1='subsector_id', column2='technology_id',
        string='Default Tech Stack',
        help="Technologies specific to this sub-sector. Added to a lead's Tech "
             "Stack on top of the industry's own defaults.",
    )
