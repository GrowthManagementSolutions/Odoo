from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Fill the four category layers on existing deal lines and template lines.

    category_id became a stored compute derived from last_categ_id (#47). Odoo
    recomputes it when the field definition changes, which blanks it until the
    layers exist -- so this backfill both fills the layers from each line's
    product category path and restores category_id through the compute.

    Sections and notes are non-accountable: their layers stay empty.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model in ('crm.deal.line', 'crm.deal.template.line'):
        Line = env[model]
        lines = Line.search([
            ('display_type', '=', False),
            ('product_id', '!=', False),
        ])
        filled = 0
        for line in lines:
            values = Line._layer_values_from_product(line.product_id)
            if any(values.values()):
                line.write(values)
                filled += 1
        # Layers are plain fields, so the derived pair needs an explicit nudge.
        env.add_to_compute(Line._fields['last_categ_id'], lines)
        env.add_to_compute(Line._fields['category_id'], lines)
        env.flush_all()

        # Non-accountable rows must carry no layers.
        cr.execute("""
            UPDATE %s
               SET layer_1_categ_id = NULL, layer_2_categ_id = NULL,
                   layer_3_categ_id = NULL, layer_4_categ_id = NULL
             WHERE display_type IS NOT NULL
        """ % Line._table)

        mismatched = Line.search([
            ('display_type', '=', False),
            ('product_id', '!=', False),
        ]).filtered(lambda l: l.category_id != l.product_id.categ_id)
        env['ir.logging'].sudo().create({
            'name': 'crm_deals.migration',
            'type': 'server',
            'level': 'WARNING' if mismatched else 'INFO',
            'dbname': cr.dbname,
            'message': '%s: layers filled on %s of %s line(s); %s line(s) whose '
                       'category does not match their product category.'
                       % (model, filled, len(lines), len(mismatched)),
            'path': 'migrations/19.0.1.0.12/post-migration.py',
            'func': 'migrate',
            'line': '0',
        })
