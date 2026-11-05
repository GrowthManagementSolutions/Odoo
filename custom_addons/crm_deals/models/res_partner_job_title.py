from odoo import fields, models


class ResPartnerJobTitle(models.Model):
    _name = 'res.partner.job.title'
    _description = 'Contact Job Title'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
