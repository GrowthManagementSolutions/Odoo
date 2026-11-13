"""Repair the Med Spa template lines' products.

`data/demo_med_spa_data.xml` passed a **product.template** XML id straight
to `product_id`, which is a **product.product** field. The two id sequences
do not line up, so every line landed on an unrelated variant - UCaaS showed
as Payment Processing, and the seeded supplier and route then had no rule
for whatever product the line actually held.

The data file now looks the variant up from its template, as
`crm_deal_template_data.xml` always did, but the records are `noupdate="1"`
and so are skipped on upgrade. This rewrites the seven existing lines.

`product_id` is a dependency of `_compute_supplier_id`, `_compute_route_id`
and `_compute_unit_price`, so writing it clears the supplier and the route
and resets the unit price to the new product's list price. The seeded
commercial values are therefore snapshotted first and written back
afterwards, in a second write so the computes have already run.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# (line xmlid, product.template xmlid, supplier xmlid, route xmlid)
LINES = [
    ('deal_template_line_med_spa_comms_ucaas',
     'product_telecommunications_ucaas',
     'partner_supplier_ringcentral', 'route_ringcentral_telarus'),
    ('deal_template_line_med_spa_comms_pots',
     'product_telecommunications_wireless_pots_replacement',
     'partner_supplier_ooma', 'route_ooma_direct'),
    ('deal_template_line_med_spa_comms_internet',
     'product_internet_service_best_effort_internet',
     'partner_supplier_comcast', 'route_comcast_sandler'),
    ('deal_template_line_med_spa_comms_security',
     'product_cybersecurity_managed_network_security',
     'partner_supplier_cyber_advisors', 'route_cyber_advisors_direct'),
    ('deal_template_line_med_spa_front_payment_processing',
     'product_payment_processing_solutions_payment_processing',
     'partner_supplier_cardconnect', 'route_cardconnect_sandler'),
    ('deal_template_line_med_spa_front_terminal',
     'product_point_of_sale_standalone_cc_terminal',
     'partner_supplier_dejavoo', 'route_dejavoo_sandler'),
    ('deal_template_line_med_spa_front_software',
     'product_practice_management_software_health_and_beauty',
     'partner_supplier_daysmart', 'route_daysmart_direct'),
]

# Seeded values the product write would otherwise restate.
KEEP = ('quantity', 'unit_price', 'estimated_monthly_cost',
        'estimated_one_time_revenue', 'processing_volume', 'contract_term')


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Product = env['product.product']

    fixed, skipped = [], []
    for line_xmlid, tmpl_xmlid, supplier_xmlid, route_xmlid in LINES:
        line = env.ref('crm_deals.%s' % line_xmlid, raise_if_not_found=False)
        template = env.ref('crm_deals.%s' % tmpl_xmlid, raise_if_not_found=False)
        if not line or not template:
            skipped.append('%s (line or product missing)' % line_xmlid)
            continue

        variant = Product.search(
            [('product_tmpl_id', '=', template.id)], limit=1)
        if not variant:
            skipped.append('%s (no variant for %s)' % (line_xmlid, template.name))
            continue
        if line.product_id == variant:
            continue

        keep = {name: line[name] for name in KEEP}
        supplier = env.ref('crm_deals.%s' % supplier_xmlid,
                           raise_if_not_found=False)
        route = env.ref('crm_deals.%s' % route_xmlid, raise_if_not_found=False)

        was = line.product_id.name or 'none'
        # First the product, letting its computes run and clear the rest.
        line.write({'product_id': variant.id})
        # Then the seeded choices back on top of them.
        restore = dict(keep)
        restore['supplier_id'] = supplier.id if supplier else False
        restore['route_id'] = route.id if route else False
        line.write(restore)
        fixed.append('%s: %s -> %s' % (line_xmlid, was, variant.name))

    _logger.info(
        'crm_deals: Med Spa template line products repaired. Fixed %s: %s. '
        'Skipped %s: %s.',
        len(fixed), '; '.join(fixed) or 'none',
        len(skipped), '; '.join(skipped) or 'none')
