# The two #36 views are gone from the module, but their stored arch is still
# in the database when views load, and writing any sibling view on
# product.template or product.supplierinfo revalidates the whole inheritance
# tree - which then trips over master_supplier_ids and the two rate fields.
# Odoo's own cleanup of records dropped from a module runs later, so they are
# deleted here first. Nothing references them.
_STALE_VIEWS = [
    'product_supplierinfo_tree_view2_commission',
    'product_template_form_master_suppliers',
]


def migrate(cr, version):
    for xmlid in _STALE_VIEWS:
        cr.execute("""
            DELETE FROM ir_ui_view
             WHERE id IN (
                SELECT res_id FROM ir_model_data
                 WHERE module = 'crm_deals' AND model = 'ir.ui.view'
                   AND name = %s)
        """, (xmlid,))
        cr.execute("""
            DELETE FROM ir_model_data
             WHERE module = 'crm_deals' AND model = 'ir.ui.view' AND name = %s
        """, (xmlid,))
