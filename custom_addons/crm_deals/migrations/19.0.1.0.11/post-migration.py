from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Backfill Default Start Date on existing leads from their create date.

    default_start_date is introduced in this version with
    ``default=fields.Date.context_today``, and Odoo applies that default to
    every existing row when it adds the column. So by the time this runs, each
    pre-existing lead already holds today's date, not NULL -- filtering on NULL
    would match nothing. Every value present is therefore the ORM's own
    initialisation, never a user's choice, which makes an unconditional
    overwrite correct here (and correct only here, for this one upgrade step).

    Written in SQL so the field's tracking does not post a message on every
    historical lead.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    if 'default_start_date' not in env['crm.lead']._fields:
        return
    cr.execute("""
        UPDATE crm_lead
           SET default_start_date = COALESCE(create_date::date, CURRENT_DATE)
    """)
    env['ir.logging'].sudo().create({
        'name': 'crm_deals.migration',
        'type': 'server',
        'level': 'INFO',
        'dbname': cr.dbname,
        'message': 'Default Start Date backfilled from create date on '
                   '%s lead(s).' % cr.rowcount,
        'path': 'migrations/19.0.1.0.11/post-migration.py',
        'func': 'migrate',
        'line': '0',
    })
