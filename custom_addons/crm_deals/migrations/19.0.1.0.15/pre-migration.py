from odoo import SUPERUSER_ID, api

# (table, model) pairs carrying No. of Locations.
_TARGETS = (
    ('crm_lead', 'crm.lead'),
    ('res_partner', 'res.partner'),
)

# Selection values are '1'..'20' plus '20+'.
_MAX = 20
_OVERFLOW = '20+'


def _column_type(cr, table, column):
    cr.execute("""
        SELECT data_type
          FROM information_schema.columns
         WHERE table_name = %s AND column_name = %s
    """, (table, column))
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    """Turn No. of Locations into a selection, mapping the existing values.

    Runs **pre**-migrate, so the data is mapped and the column retyped before
    the ORM compares the new Selection field against the old column. Mapping,
    on both crm.lead and res.partner:

        0 or empty -> empty
        1-20       -> the matching value
        above 20   -> '20+'

    The field was an Integer in this repository, but the numeric-text case is
    handled too, in case a database carries it as Char: numeric text maps the
    same way and anything non-numeric is cleared, with the affected ids listed
    in the upgrade log.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    notes = []

    for table, model in _TARGETS:
        data_type = _column_type(cr, table, 'location_count')
        if data_type is None:
            # Field never materialised on this database; the ORM will add the
            # column in its new shape.
            continue
        if data_type in ('character varying', 'text'):
            # Report, then clear, values that are not plain digits.
            cr.execute("""
                SELECT id, location_count
                  FROM %s
                 WHERE location_count IS NOT NULL
                   AND btrim(location_count) <> ''
                   AND btrim(location_count) !~ '^[0-9]+$'
                 ORDER BY id
            """ % table)
            unparsable = cr.fetchall()
            if unparsable:
                notes.append(
                    '%s: cleared %s non-numeric No. of Locations value(s): %s'
                    % (model, len(unparsable), ', '.join(
                        'id=%s (%r)' % (rid, val) for rid, val in unparsable))
                )
            cr.execute("""
                ALTER TABLE %s
                ALTER COLUMN location_count TYPE varchar
                USING CASE
                    WHEN location_count IS NULL THEN NULL
                    WHEN btrim(location_count) !~ '^[0-9]+$' THEN NULL
                    WHEN btrim(location_count)::numeric <= 0 THEN NULL
                    WHEN btrim(location_count)::numeric > %%s THEN %%s
                    ELSE btrim(location_count)::numeric::bigint::varchar
                END
            """ % table, (_MAX, _OVERFLOW))
        else:
            # Integer, bigint or numeric.
            cr.execute("""
                ALTER TABLE %s
                ALTER COLUMN location_count TYPE varchar
                USING CASE
                    WHEN location_count IS NULL THEN NULL
                    WHEN location_count <= 0 THEN NULL
                    WHEN location_count > %%s THEN %%s
                    ELSE location_count::bigint::varchar
                END
            """ % table, (_MAX, _OVERFLOW))

        cr.execute("""
            SELECT count(*) FROM %s WHERE location_count IS NOT NULL
        """ % table)
        notes.append('%s: %s record(s) carry a No. of Locations value.'
                     % (model, cr.fetchone()[0]))

    if notes:
        env['ir.logging'].sudo().create({
            'name': 'crm_deals.migration',
            'type': 'server',
            'level': 'INFO',
            'dbname': cr.dbname,
            'message': 'No. of Locations converted to a selection. '
                       + ' '.join(notes),
            'path': 'migrations/19.0.1.0.15/pre-migration.py',
            'func': 'migrate',
            'line': '0',
        })
