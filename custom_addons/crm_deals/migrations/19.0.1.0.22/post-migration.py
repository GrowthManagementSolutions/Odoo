from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Seed the GMS pipeline stages on a database that already has the module.

    The fresh-install path is the module's post_init_hook; both call the same
    method, and the ir.config_parameter it sets means whichever runs first is
    the only one that does anything. Running this upgrade again - or any
    later upgrade - never touches the stages, so a rename or reorder made in
    the UI stands.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['crm.stage']._seed_gms_pipeline_stages()
