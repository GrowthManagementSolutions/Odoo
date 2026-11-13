"""#57 - quantity and unit price come back and drive the monthly charge.

The two columns are created and filled here, before the ORM reaches them, for
two reasons. A static default would fill existing section and note rows with
a quantity of 1 and break the non-accountable constraint the same update adds;
and creating the columns ourselves stops Odoo mass-computing
`estimated_monthly_cost`, which is becoming a stored compute of the pair.

Every real line gets quantity 1 and a unit price equal to its current MRC, so
quantity x unit price reproduces the stored figure exactly and no amount moves.
"""
import logging

_logger = logging.getLogger(__name__)

_COLUMNS = (
    ('quantity', 'double precision'),
    ('unit_price', 'numeric'),
)


def migrate(cr, version):
    for column, ctype in _COLUMNS:
        cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = 'crm_deal_line' AND column_name = %s
        """, (column,))
        if not cr.fetchone():
            cr.execute(
                'ALTER TABLE crm_deal_line ADD COLUMN %s %s' % (column, ctype))

    # Real lines: quantity 1 at the charge they already carry.
    cr.execute("""
        UPDATE crm_deal_line
           SET quantity = 1,
               unit_price = COALESCE(estimated_monthly_cost, 0)
         WHERE display_type IS NULL
    """)
    real = cr.rowcount
    # Sections and notes stay non-accountable.
    cr.execute("""
        UPDATE crm_deal_line
           SET quantity = 0, unit_price = 0
         WHERE display_type IS NOT NULL
    """)
    _logger.info(
        'crm_deals #57: %s deal line(s) set to quantity 1 at their current '
        'MRC; %s section/note row(s) left at zero', real, cr.rowcount)
