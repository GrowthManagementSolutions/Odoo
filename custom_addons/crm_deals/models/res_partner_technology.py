from odoo import fields, models


class ResPartnerTechnology(models.Model):
    _name = 'res.partner.technology'
    _description = 'Partner Technology'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    color = fields.Integer(string='Color')
