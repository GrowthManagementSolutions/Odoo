{
    "name": "Supplier Onboarding",
    "version": "1.0",
    "summary": "Supplier onboarding with NDA workflow",
    "category": "Operations",
    "author": "GMS",
    "depends": [
        "base",
        "mail",
        "contacts",
        "gms_client_proposals",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/nda_email_template.xml",
        "views/supplier_onboarding_views.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}