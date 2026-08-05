{
    "name": "GMS Sales Flow",
    "version": "19.0.1.1.2",
    "summary": "GMS CRM intake, routing, and sales-flow foundation",
    "description": """
GMS Sales Flow
==============

Features:
- Two GMS CRM teams
- Shared GMS stage flow
- Lead status taxonomy
- Sales channel classification
- Lead source classification
- Odoo 19 security roles
- Direct lead webform
- Channel lead webform
- Automatic team routing
- SA/CM notification activities
- CRM search filters
- Sales-team opportunity sharing
    """,
    "category": "Sales/CRM",
    "author": "Growth Management Solutions",
    "license": "OPL-1",
    "depends": [
        "base",
        "crm",
        "sales_team",
        "mail",
        "website",
    ],
    "data": [
        "security/security.xml",
        "data/crm_team_data.xml",
        "data/crm_stage_data.xml",
        "views/crm_lead_views.xml",
        "views/lead_webform_templates.xml",
        "wizard/opportunity_intake_wizard_views.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}