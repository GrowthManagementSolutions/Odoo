from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Backfill Config Document IDs, and drop the removed subscriber table.

    Documents are numbered in create-date order so the CFG sequence follows the
    order they were actually created in. Anything that already carries an ID is
    left alone; '/' is treated as missing because that is the fallback create()
    used when the sequence could not be reached.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    documents = env['config.document'].search(
        ['|', ('reference', '=', False), ('reference', '=', '/')],
        order='create_date asc, id asc',
    )
    sequence = env['ir.sequence']
    for document in documents:
        reference = sequence.next_by_code('config.document')
        if reference:
            document.reference = reference

    # subscriber_ids was removed (#47); its relation table is now orphaned.
    cr.execute("DROP TABLE IF EXISTS config_document_subscriber_rel")
