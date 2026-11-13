from odoo import SUPERUSER_ID, api

# (xmlid, exact contact name) - generated with the data file.
CONTACTS = [('partner_supplier_marco', 'Marco'), ('partner_supplier_cyber_advisors', 'Cyber Advisors'), ('partner_supplier_integrated_computer_services', 'Integrated Computer Services'), ('partner_supplier_critical_coordination', 'Critical Coordination'), ('partner_supplier_microsoft_azure', 'Microsoft Azure'), ('partner_supplier_giltech', 'Giltech'), ('partner_supplier_for2fi', 'For2Fi'), ('partner_supplier_comcast', 'Comcast'), ('partner_supplier_lumen', 'Lumen'), ('partner_supplier_verizon', 'Verizon'), ('partner_supplier_spectrum', 'Spectrum'), ('partner_supplier_ringcentral', 'RingCentral'), ('partner_supplier_windstream_enterprise', 'Windstream Enterprise'), ('partner_supplier_ooma', 'Ooma'), ('partner_supplier_directv', 'DIRECTV'), ('partner_supplier_clover', 'Clover'), ('partner_supplier_dejavoo', 'Dejavoo'), ('partner_supplier_square', 'Square'), ('partner_supplier_finale_inventory', 'Finale Inventory'), ('partner_supplier_ach_com', 'ACH.com'), ('partner_supplier_cardconnect', 'CardConnect'), ('partner_supplier_midwest_atm', 'Midwest ATM'), ('partner_supplier_rectangle_health', 'Rectangle Health'), ('partner_supplier_aspire_software', 'Aspire Software'), ('partner_supplier_monday_com', 'Monday.com'), ('partner_supplier_daysmart', 'Daysmart'), ('partner_supplier_onpay', 'onPay'), ('partner_supplier_gusto', 'Gusto'), ('partner_supplier_buddy_punch', 'Buddy Punch'), ('partner_supplier_worry_free_bookkeeping', 'Worry Free Bookkeeping'), ('partner_supplier_trileaf_designs', 'TriLeaf Designs'), ('partner_supplier_adheft_marketing', 'Adheft Marketing'), ('partner_supplier_digital_matrix', 'Digital Matrix'), ('partner_supplier_advance_marketing_group', 'Advance Marketing Group'), ('partner_master_supplier_mettel', 'MetTel'), ('partner_master_supplier_granite', 'Granite'), ('partner_master_supplier_priority_commerce', 'Priority Commerce'), ('partner_master_supplier_asset_black_momentum', 'Asset Black / Momentum')]


def migrate(cr, version):
    """Adopt supplier/master-supplier contacts that already exist by exact name.

    Registering them under the ids the data file uses means the noupdate
    records match the existing contacts instead of creating duplicates.
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
