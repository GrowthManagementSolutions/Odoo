from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Align adopted service products with the settings this data file declares.

    Records that pre-dated the data file are matched by XML id and protected by
    noupdate, so their service_tracking was left at whatever it had ('no').
    That silently disables the deal->project/task generation, so bring them in
    line with the rest of the catalogue.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    registered = env['ir.model.data'].search([
        ('module', '=', 'crm_deals'),
        ('model', '=', 'product.template'),
    ])
    products = env['product.template'].browse(registered.mapped('res_id')).exists()
    stale = products.filtered(lambda p: p.service_tracking != 'task_in_project')
    if stale:
        stale.write({'service_tracking': 'task_in_project'})
