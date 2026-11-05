{
    'name': 'CRM Deals',
    'version': '19.0.1.0.35',
    'category': 'Sales/CRM',
    'summary': 'Adds a Deals page to the opportunity form',
    'depends': [
        'crm', 'contacts', 'sale_project', 'sign', 'portal', 'sale_crm', 'purchase',
        'project', 'helpdesk',
    ],
    'data': [
        'security/crm_deals_groups.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/res_partner_category_data.xml',
        'data/res_partner_industry_data.xml',
        'data/res_partner_subsector_data.xml',
        'data/res_partner_job_title_data.xml',
        'data/res_partner_technology_data.xml',
        'data/product_service_data.xml',
        'data/product_tag_data.xml',
        'data/res_partner_supplier_data.xml',
        # After the partner tags it references (#63). The demo users' sales
        # team membership is not here - Agent Channel does not exist until
        # the post_init_hook runs - see crm.team._seed_demo_user_teams.
        #'data/demo_users_data.xml',
        'data/crm_deal_template_data.xml',
        'data/product_supplier_route_data.xml',
        'data/demo_med_spa_data.xml',
        # After the Med Spa sub-sector: this file is only a <function>
        # call, and it fills the Default Tech Stack of every sub-sector
        # loaded before it.
        'data/res_partner_technology_default_data.xml',
        'data/config_document_type_data.xml',
        'data/config_terminal_type_data.xml',
        'data/crm_lead_budget_data.xml',
        'wizard/crm_deal_line_wizard_views.xml',
        'views/product_master_agreement_views.xml',
        'views/product_supplier_route_views.xml',
        'views/product_views.xml',
        'views/crm_stage_views.xml',
        'views/crm_deal_line_views.xml',
        'views/config_document_type_views.xml',
        'views/config_terminal_type_views.xml',
        'views/config_document_views.xml',
        'views/crm_deal_commission_views.xml',
        'views/crm_deal_template_views.xml',
        'views/crm_lead_views.xml',
        'views/crm_lead_server_actions.xml',
        'views/res_partner_subsector_views.xml',
        'views/res_partner_industry_views.xml',
        'views/res_partner_job_title_views.xml',
        'views/res_partner_technology_views.xml',
        'views/res_partner_views.xml',
        'views/project_task_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/crm_deals_portal_templates.xml',
        'views/crm_deals_portal_form_templates.xml',
        'views/crm_deals_budget_portal_templates.xml',
        'report/crm_lead_budget_report.xml',
    ],
    'assets': {
        # Scoped per bundle since #58: the kanban widgets are backend-only and
        # the Budget Summary page is frontend-only.
        'web.assets_backend': [
            'crm_deals/static/src/kanban/**/*',
        ],
        'web.assets_frontend': [
            'crm_deals/static/src/portal/**/*',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
}