from odoo import fields, models


class ConfigTerminalType(models.Model):
    _name = 'config.terminal.type'
    _description = 'Terminal Type'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
