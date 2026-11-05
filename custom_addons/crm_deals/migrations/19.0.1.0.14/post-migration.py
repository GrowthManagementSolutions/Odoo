from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Drop the industry-level Default Tech Stack relation table.

    #50 shipped ``res.partner.industry.default_technology_ids``; the feature is
    now sub-sector only, so the field is gone from the model. Odoo removes the
    field's registry row on upgrade but leaves a many2many's relation table
    behind, so it is dropped here. The sub-sector table
    (``res_partner_subsector_default_technology_rel``) is deliberately
    untouched - that side of the feature stays.
    """
    cr.execute("DROP TABLE IF EXISTS res_partner_industry_default_technology_rel")
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['ir.logging'].sudo().create({
        'name': 'crm_deals.migration',
        'type': 'server',
        'level': 'INFO',
        'dbname': cr.dbname,
        'message': 'Industry-level Default Tech Stack removed: relation table '
                   'res_partner_industry_default_technology_rel dropped.',
        'path': 'migrations/19.0.1.0.14/post-migration.py',
        'func': 'migrate',
        'line': '0',
    })
