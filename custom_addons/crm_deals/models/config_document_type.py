from odoo import fields, models

# Drives which type-specific section the document form shows. Kept on the type
# (rather than hardcoded per type) so a new type can reuse an existing section
# from the UI, without code.
DETAIL_SECTION_SELECTION = [
    ('none', 'None'),
    ('telecom', 'Telecom'),
    ('internet_data', 'Internet/Data'),
    ('payment_processing', 'Payment Processing'),
]


class ConfigDocumentType(models.Model):
    _name = 'config.document.type'
    _description = 'Configuration Document Type'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    detail_section = fields.Selection(
        selection=DETAIL_SECTION_SELECTION,
        string='Detail Section',
        default='none',
        required=True,
        help="Which set of type-specific fields the configuration document "
             "form shows for this type.",
    )
