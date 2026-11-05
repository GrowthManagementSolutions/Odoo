from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Point the three launch types at their detail section.

    The #43 types were loaded with noupdate="1", so adding the value to the
    data file would not reach the existing records. Only types still on the
    default are touched, so a value set by hand from the UI survives.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    sections = {
        'crm_deals.config_document_type_ucaas': 'telecom',
        'crm_deals.config_document_type_internet_service': 'internet_data',
        'crm_deals.config_document_type_payment_processing': 'payment_processing',
    }
    for xmlid, section in sections.items():
        document_type = env.ref(xmlid, raise_if_not_found=False)
        if document_type and document_type.detail_section in ('none', False):
            document_type.detail_section = section
