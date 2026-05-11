{
    "name": "GMS Client Proposals",
    "version": "19.0.1.0.0",
    "summary": "Client proposal, SOW, revision, acknowledgment, and forecast seed workflow",
    "category": "Sales/CRM",
    "author": "GMS",
    "license": "OPL-1",
   "depends": [
        "base",
        "contacts",
        "crm",
        "mail",
        "product",
    ],
    "data": [
    "security/security.xml",
    "security/ir.model.access.csv",

    "data/ir_sequence_data.xml",
    "data/cron_data.xml",

    "views/res_partner_views.xml",
    "views/crm_lead_views.xml",
    "views/product_views.xml",

    "views/client_proposal_views.xml",
    "views/proposal_rate_table_views.xml",
    "views/sow_template_views.xml",
    "views/proposal_menu.xml",

    "views/payout_views.xml",

    "wizard/proposal_convert_wizard_views.xml",

    "report/proposal_report.xml",
    "report/proposal_report_templates.xml",
        
    ],
    "installable": True,
    "application": True,
}