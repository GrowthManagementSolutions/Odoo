{
    "name": "GMS Sales Flow",
    "version": "19.0.1.1.0",
    "summary": "GMS CRM intake, routing, and sales-flow foundation",
    "description": """
GMS Sales Flow - Week 1
=======================

Week 1A:
- Two GMS CRM teams
- Shared GMS stage flow
- Lead status taxonomy
- Sales channel classification
- Lead source classification
- Odoo 19 security roles

Week 1B:
- Direct lead webform
- Channel lead webform
- Automatic team routing
- SA/CM notification activities
- CRM search filters
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
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}