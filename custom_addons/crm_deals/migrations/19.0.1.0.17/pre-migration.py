from odoo import SUPERUSER_ID, api

# (xmlid, exact contact name) - the contacts #53's data file creates. Square
# is already adopted by 19.0.1.0.6 and is not repeated here.
CONTACTS = [
    ('partner_supplier_broadvoice', 'Broadvoice'),
    ('partner_supplier_zoom', 'Zoom'),
    ('partner_supplier_cci_network_services', 'CCI Network Services'),
    ('partner_master_supplier_sandler_partners', 'Sandler Partners'),
    ('partner_master_supplier_telarus', 'Telarus'),
]


def migrate(cr, version):
    """Adopt #53's supplier and master-supplier contacts by exact name.

    Same pattern as 19.0.1.0.6: registering an existing contact under the id
    the data file uses means the noupdate record matches it instead of
    creating a duplicate. Runs pre-migrate, before the data file loads.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env['res.partner']
    Data = env['ir.model.data']
    for xmlid, name in CONTACTS:
        if Data.search_count([('module', '=', 'crm_deals'), ('name', '=', xmlid)]):
            continue
        partner = Partner.search([('name', '=', name)], limit=1)
        if partner:
            Data.create({
                'module': 'crm_deals', 'name': xmlid, 'model': 'res.partner',
                'res_id': partner.id, 'noupdate': True,
            })
