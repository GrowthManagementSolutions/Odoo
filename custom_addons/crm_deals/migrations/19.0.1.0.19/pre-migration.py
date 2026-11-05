def _has_column(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Snapshot each deal line's supplier and master supplier before #54.

    ``master_supplier_id`` stops being a stored compute and becomes related to
    ``route_id.master_id``. Odoo recomputes it during the upgrade, and since no
    line has a route yet it would blank every existing value. The pair is
    copied aside here so the post-migration can derive the matching route and
    the master supplier comes back by itself.
    """
    if not _has_column(cr, 'crm_deal_line', 'master_supplier_id'):
        return
    cr.execute("DROP TABLE IF EXISTS crm_deals_54_route_backfill")
    cr.execute("""
        CREATE TABLE crm_deals_54_route_backfill AS
        SELECT id, supplier_id, master_supplier_id
          FROM crm_deal_line
         WHERE supplier_id IS NOT NULL
    """)
