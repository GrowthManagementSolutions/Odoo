from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Backfill supplier / master supplier on existing deal template lines.

    The #40 templates were loaded with noupdate="1", so editing the data file
    cannot reach them. Fill only empty values, using the same rule as the
    computes; anything already set is left alone.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['crm.deal.template.line'].search([
        ('display_type', '=', False),
        ('product_id', '!=', False),
        '|', ('supplier_id', '=', False), ('master_supplier_id', '=', False),
    ])
    for line in lines:
        vals = {}
        if not line.supplier_id:
            supplier = line._default_supplier_id()
            if supplier:
                vals['supplier_id'] = supplier.id
        if not line.master_supplier_id:
            master = line._default_master_supplier_id()
            if master:
                vals['master_supplier_id'] = master.id
        if vals:
            line.write(vals)
