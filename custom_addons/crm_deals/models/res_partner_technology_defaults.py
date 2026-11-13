"""Starting Default Tech Stack for the seeded sub-sectors.

The Default Tech Stack is a sub-sector-level concept only - the industry
carries none. The sub-sector records ship with ``noupdate="1"``, so they
cannot be given these values by redefining them: an upgrade would skip the
change. They are applied instead by ``_seed_default_technologies()``, called from
``data/res_partner_technology_default_data.xml``, which only ever fills a
Default Tech Stack that is still empty.

Keys are XML ids without the ``crm_deals.`` prefix; technologies are named
without their ``tech_`` prefix. Nothing here creates a record - every name
must already be loaded by the module.
"""

from odoo import Command, api, models

# Three to eight technologies specific to the sub-sector. The industry level
# was removed in favour of sub-sector only, so these stand alone.
SUBSECTOR_DEFAULTS = {
    # Agriculture
    'subsector_agriculture_farm_and_ranch': [
        'mobility', 'physical_security_security_cameras', 'energy', 'payroll',
        'robotics'],
    'subsector_agriculture_nursery_and_greenhouse': [
        'full_point_of_sale_systems', 'payment_processing',
        'inventory_management', 'ecommerce'],
    'subsector_agriculture_agricultural_supply': [
        'full_point_of_sale_systems', 'inventory_management',
        'payment_processing', 'invoicing_system', 'waste_garbage_hauling'],
    # Amusement Parks
    'subsector_amusement_parks_theme_park': [
        'full_point_of_sale_systems', 'digital_signage', 'self_order_kiosk',
        'employee_scheduling', 'gift_cards', 'event_management'],
    'subsector_amusement_parks_water_park': [
        'full_point_of_sale_systems', 'self_order_kiosk',
        'employee_scheduling', 'gift_cards', 'time_clock'],
    'subsector_amusement_parks_family_entertainment_center': [
        'full_point_of_sale_systems', 'gift_cards', 'online_ordering',
        'digital_signage', 'streaming'],
    # Arts And Entertainment
    'subsector_arts_and_entertainment_theater': [
        'full_point_of_sale_systems', 'digital_signage', 'streaming',
        'event_management', 'gift_cards'],
    'subsector_arts_and_entertainment_museum_and_gallery': [
        'full_point_of_sale_systems', 'physical_security_security_cameras',
        'digital_signage', 'web_design', 'event_management'],
    'subsector_arts_and_entertainment_live_music_venue': [
        'full_point_of_sale_systems', 'event_management', 'streaming',
        'employee_scheduling', 'social_media_consulting'],
    # Automotive
    'subsector_automotive_auto_repair': [
        'crm', 'invoicing_system', 'physical_security_security_cameras',
        'inventory_management', 'digital_marketing'],
    'subsector_automotive_car_dealership': [
        'crm', 'digital_marketing', 'physical_security_security_cameras',
        'leasing', 'loans', 'web_design'],
    'subsector_automotive_car_wash': [
        'full_point_of_sale_systems', 'self_order_kiosk',
        'physical_security_security_cameras', 'employee_scheduling'],
    # Barber Shop
    'subsector_barber_shop_traditional_barber': [
        'employee_scheduling', 'gift_cards', 'social_media_consulting',
        'streaming'],
    'subsector_barber_shop_men_s_grooming_lounge': [
        'employee_scheduling', 'gift_cards', 'digital_marketing', 'streaming',
        'digital_signage'],
    # Campground
    'subsector_campground_rv_park': [
        'full_point_of_sale_systems', 'physical_security_security_cameras',
        'energy', 'waste_garbage_hauling', 'web_design'],
    'subsector_campground_tent_campground': [
        'full_point_of_sale_systems', 'physical_security_security_cameras',
        'waste_garbage_hauling', 'web_design'],
    # Chiropractic Clinic
    'subsector_chiropractic_clinic_single_practitioner': [
        'payment_processing', 'cybersecurity', 'employee_scheduling',
        'web_design'],
    'subsector_chiropractic_clinic_multi_provider_practice': [
        'payment_processing', 'cybersecurity', 'payroll',
        'employee_scheduling', 'physical_security_security_cameras',
        'human_resources'],
    # Construction
    'subsector_construction_residential': [
        'crm', 'invoicing_system', 'payment_processing', 'payroll',
        'digital_marketing'],
    'subsector_construction_commercial': [
        'crm', 'commercial_construction', 'invoicing_system', 'payroll',
        'structured_low_voltage_cabling', 'accounts_payable_automation'],
    'subsector_construction_specialty_trades': [
        'invoicing_system', 'payment_processing', 'employee_scheduling',
        'time_clock', 'low_voltage_integration'],
    # Digital Marketing/Marketing
    'subsector_digital_marketing_marketing_agency': [
        'seo', 'social_media_consulting', 'content_creation',
        'graphics_design', 'web_design', 'video_production'],
    'subsector_digital_marketing_marketing_freelance_consultant': [
        'seo', 'content_creation', 'social_media_consulting',
        'invoicing_system', 'virtual_assistance'],
    # Dispensary
    'subsector_dispensary_medical': [
        'inventory_management', 'cybersecurity', 'security_monitoring', 'atm'],
    'subsector_dispensary_recreational': [
        'inventory_management', 'digital_signage', 'atm',
        'security_monitoring', 'self_order_kiosk'],
    # E-Commerce - Retail
    'subsector_e_commerce_retail_direct_to_consumer_brand': [
        'shopping_carts', 'web_design', 'seo', 'digital_marketing',
        'inventory_management', 'social_media_consulting'],
    'subsector_e_commerce_retail_marketplace_seller': [
        'shopping_carts', 'inventory_management', 'seo', 'data_services',
        'virtual_assistance'],
    'subsector_e_commerce_retail_subscription_box': [
        'shopping_carts', 'inventory_management', 'crm', 'digital_marketing',
        'invoicing_system'],
    # E-Commerce - Wholesale
    'subsector_e_commerce_wholesale_b2b_distributor': [
        'inventory_management', 'crm', 'invoicing_system',
        'accounts_payable_automation', 'ach_services'],
    'subsector_e_commerce_wholesale_online_wholesale_marketplace': [
        'shopping_carts', 'inventory_management', 'data_services',
        'web_hosting', 'seo'],
    # Education
    'subsector_education_k_12_school': [
        'physical_security_security_cameras', 'microsoft_licensing',
        'google_licensing', 'lan_management', 'security_system'],
    'subsector_education_higher_education': [
        'physical_security_security_cameras', 'microsoft_licensing',
        'lan_management', 'conferencing', 'data_services', 'managed_it'],
    'subsector_education_tutoring_and_training_center': [
        'conferencing', 'employee_scheduling', 'payment_processing',
        'web_design'],
    # Event Center
    'subsector_event_center_banquet_hall': [
        'full_point_of_sale_systems', 'payment_processing', 'digital_signage',
        'employee_scheduling', 'streaming'],
    'subsector_event_center_conference_center': [
        'conferencing', 'digital_signage', 'payment_processing',
        'lan_management', 'streaming'],
    'subsector_event_center_wedding_venue': [
        'payment_processing', 'web_design', 'social_media_consulting',
        'digital_media'],
    # Fairs/Festivals
    'subsector_fairs_festivals_county_fair': [
        'full_point_of_sale_systems', 'mobility',
        'physical_security_security_cameras', 'waste_garbage_hauling'],
    'subsector_fairs_festivals_music_festival': [
        'full_point_of_sale_systems', 'mobility', 'streaming',
        'physical_security_security_cameras', 'digital_signage'],
    'subsector_fairs_festivals_food_festival': [
        'full_point_of_sale_systems', 'mobility', 'standalone_cc_terminal',
        'waste_garbage_hauling'],
    # Finance And Insurance
    'subsector_finance_and_insurance_insurance_agency': [
        'crm', 'contact_center', 'digital_marketing', 'web_design',
        'invoicing_system'],
    'subsector_finance_and_insurance_credit_union': [
        'atm', 'banking', 'ach_services',
        'physical_security_security_cameras', 'contact_center', 'managed_it'],
    'subsector_finance_and_insurance_financial_advisory': [
        'crm', 'cpas_and_advisors', 'conferencing', 'web_design',
        'data_services'],
    # Food Truck
    'subsector_food_truck_single_truck': [
        'standalone_cc_terminal', 'receipt_printers', 'online_ordering',
        'social_media_consulting'],
    'subsector_food_truck_fleet': [
        'online_ordering', 'employee_scheduling', 'inventory_management',
        'gift_cards', 'digital_marketing'],
    # Full Service Restaurant
    'subsector_full_service_restaurant_casual_dining': [
        'kitchen_bar_printers', 'kitchen_display_system_kds_hardware',
        'online_ordering', 'gift_cards', 'employee_scheduling',
        'inventory_management'],
    'subsector_full_service_restaurant_fine_dining': [
        'kitchen_bar_printers', 'kitchen_display_system_kds_hardware',
        'gift_cards', 'employee_scheduling', 'digital_marketing',
        'inventory_management'],
    'subsector_full_service_restaurant_bar_and_grill': [
        'kitchen_bar_printers', 'kitchen_display_system_kds_hardware',
        'online_ordering', 'gift_cards', 'streaming', 'employee_scheduling'],
    # General Contractor
    'subsector_general_contractor_residential': [
        'crm', 'invoicing_system', 'payment_processing', 'digital_marketing',
        'payroll'],
    'subsector_general_contractor_commercial': [
        'crm', 'commercial_construction', 'invoicing_system',
        'accounts_payable_automation', 'structured_low_voltage_cabling',
        'payroll'],
    # Golf Course
    'subsector_golf_course_public_course': [
        'employee_scheduling', 'gift_cards', 'web_design', 'digital_signage',
        'physical_security_security_cameras'],
    'subsector_golf_course_private_club': [
        'crm', 'gift_cards', 'employee_scheduling', 'invoicing_system',
        'streaming', 'event_management'],
    'subsector_golf_course_driving_range': [
        'self_order_kiosk', 'digital_signage', 'employee_scheduling',
        'gift_cards'],
    # Government
    'subsector_government_municipal': [
        'physical_security_security_cameras', 'contact_center', 'managed_it',
        'structured_low_voltage_cabling', 'data_services'],
    'subsector_government_county': [
        'physical_security_security_cameras', 'contact_center', 'managed_it',
        'data_services', 'microsoft_licensing'],
    'subsector_government_state_agency': [
        'contact_center', 'managed_it', 'data_services',
        'microsoft_licensing', 'conferencing'],
    # Health And Social Care
    'subsector_health_and_social_care_home_health': [
        'mobility', 'employee_scheduling', 'payroll',
        'practice_management_software', 'time_clock'],
    'subsector_health_and_social_care_assisted_living': [
        'physical_security_security_cameras', 'employee_scheduling', 'payroll',
        'security_monitoring', 'streaming', 'practice_management_software'],
    'subsector_health_and_social_care_social_services': [
        'crm', 'contact_center', 'payroll', 'conferencing', 'human_resources'],
    # Information Technology
    'subsector_information_technology_managed_service_provider': [
        'managed_it', 'it_services', 'lan_management', 'hardware_aggregation',
        'microsoft_licensing', 'naas'],
    'subsector_information_technology_it_consulting': [
        'it_professional_services', 'microsoft_licensing', 'conferencing',
        'crm', 'data_services'],
    # Integrated Clinic
    'subsector_integrated_clinic_multi_specialty': [
        'cybersecurity', 'payment_processing', 'payroll',
        'physical_security_security_cameras', 'human_resources', 'managed_it'],
    'subsector_integrated_clinic_physical_therapy_and_rehab': [
        'cybersecurity', 'payment_processing', 'employee_scheduling',
        'payroll', 'web_design'],
    # Liquor Store
    'subsector_liquor_store_standalone': [
        'inventory_management', 'physical_security_security_cameras', 'atm',
        'receipt_printers'],
    'subsector_liquor_store_chain': [
        'inventory_management', 'physical_security_security_cameras',
        'employee_scheduling', 'digital_signage', 'data_services'],
    # Lodging
    'subsector_lodging_hotel': [
        'physical_security_security_cameras', 'streaming',
        'employee_scheduling', 'digital_signage', 'conferencing',
        'event_management'],
    'subsector_lodging_motel': [
        'physical_security_security_cameras', 'streaming', 'web_design',
        'security_system'],
    'subsector_lodging_bed_and_breakfast': [
        'web_design', 'streaming', 'social_media_consulting',
        'full_point_of_sale_systems'],
    # Logistics
    'subsector_logistics_warehousing': [
        'inventory_management', 'physical_security_security_cameras',
        'lan_management', 'robotics', 'structured_low_voltage_cabling'],
    'subsector_logistics_freight_brokerage': [
        'crm', 'invoicing_system', 'contact_center',
        'accounts_payable_automation', 'data_services'],
    'subsector_logistics_last_mile_delivery': [
        'employee_scheduling', 'time_clock', 'crm', 'invoicing_system',
        'data_services'],
    # Manufacturing
    'subsector_manufacturing_food_and_beverage': [
        'inventory_management', 'physical_security_security_cameras',
        'robotics', 'payroll', 'waste_garbage_hauling'],
    'subsector_manufacturing_industrial_equipment': [
        'inventory_management', 'crm', 'robotics', 'invoicing_system',
        'structured_low_voltage_cabling', 'lan_management'],
    'subsector_manufacturing_consumer_goods': [
        'inventory_management', 'ecommerce', 'crm', 'digital_marketing',
        'payroll'],
    # Medical Clinic
    'subsector_medical_clinic_primary_care': [
        'practice_management_software', 'cybersecurity', 'payment_processing',
        'contact_center', 'payroll'],
    'subsector_medical_clinic_med_spa': [
        'practice_management_software', 'payment_processing', 'cybersecurity',
        'digital_marketing', 'crm'],
    'subsector_medical_clinic_urgent_care': [
        'practice_management_software', 'cybersecurity', 'payment_processing',
        'employee_scheduling', 'physical_security_security_cameras'],
    'subsector_medical_clinic_dental': [
        'practice_management_software', 'cybersecurity',
        'physical_security_security_cameras', 'payroll'],
    # Mining
    'subsector_mining_aggregates_and_quarrying': [
        'physical_security_security_cameras', 'inventory_management',
        'invoicing_system', 'payroll', 'energy'],
    'subsector_mining_metal_mining': [
        'physical_security_security_cameras', 'lan_management', 'payroll',
        'energy', 'data_services'],
    # Non-Profit
    'subsector_non_profit_charity': [
        'crm', 'web_design', 'digital_marketing', 'social_media_consulting',
        'event_management'],
    'subsector_non_profit_religious_organization': [
        'streaming', 'web_design', 'digital_signage', 'event_management',
        'physical_security_security_cameras'],
    'subsector_non_profit_foundation': [
        'crm', 'web_design', 'bookkeeping', 'conferencing', 'data_services'],
    # Other
    'subsector_other_general': [
        'full_point_of_sale_systems', 'cybersecurity', 'web_design',
        'managed_it'],
    # Professional Services
    'subsector_professional_services_legal': [
        'crm', 'managed_it', 'conferencing', 'print_copy_management',
        'invoicing_system', 'data_services'],
    'subsector_professional_services_accounting': [
        'bookkeeping', 'tax_preparation', 'cpas_and_advisors',
        'accounts_payable_automation', 'invoicing_system', 'payroll'],
    'subsector_professional_services_consulting': [
        'crm', 'conferencing', 'invoicing_system', 'web_design',
        'business_coaching'],
    # Quick Service
    'subsector_quick_service_fast_food': [
        'self_order_kiosk', 'kitchen_display_system_kds_hardware',
        'online_ordering', 'digital_signage', 'employee_scheduling',
        'receipt_printers'],
    'subsector_quick_service_coffee_shop': [
        'online_ordering', 'gift_cards', 'digital_signage',
        'employee_scheduling', 'streaming'],
    'subsector_quick_service_pizza': [
        'online_ordering', 'kitchen_bar_printers',
        'kitchen_display_system_kds_tablet', 'gift_cards',
        'employee_scheduling'],
    # Real Estate
    'subsector_real_estate_brokerage': [
        'digital_marketing', 'web_design', 'seo', 'social_media_consulting',
        'conferencing'],
    'subsector_real_estate_property_management': [
        'invoicing_system', 'payment_processing',
        'physical_security_security_cameras', 'ach_services',
        'accounts_payable_automation'],
    # Retail
    'subsector_retail_apparel': [
        'inventory_management', 'ecommerce', 'gift_cards',
        'digital_marketing', 'receipt_printers'],
    'subsector_retail_convenience_store': [
        'inventory_management', 'atm', 'physical_security_security_cameras',
        'receipt_printers', 'digital_signage'],
    'subsector_retail_specialty_retail': [
        'inventory_management', 'ecommerce', 'gift_cards', 'web_design',
        'social_media_consulting'],
    # Salon
    'subsector_salon_hair_salon': [
        'employee_scheduling', 'gift_cards', 'social_media_consulting',
        'digital_marketing', 'streaming'],
    'subsector_salon_nail_salon': [
        'employee_scheduling', 'gift_cards', 'social_media_consulting',
        'streaming'],
    # Smoke/Vape Shop
    'subsector_smoke_vape_shop_smoke_shop': [
        'inventory_management', 'physical_security_security_cameras', 'atm',
        'receipt_printers'],
    'subsector_smoke_vape_shop_vape_shop': [
        'inventory_management', 'physical_security_security_cameras',
        'ecommerce', 'digital_signage'],
    # Software
    'subsector_software_saas': [
        'web_hosting', 'data_services', 'crm', 'custom_software',
        'artificial_intelligence_ai', 'microsoft_licensing'],
    'subsector_software_custom_development': [
        'custom_software', 'custom_app', 'web_hosting',
        'it_professional_services', 'conferencing'],
    # Spa
    'subsector_spa_day_spa': [
        'employee_scheduling', 'gift_cards', 'social_media_consulting',
        'streaming', 'digital_marketing'],
    'subsector_spa_med_spa': [
        'employee_scheduling', 'gift_cards', 'practice_management_software',
        'digital_marketing', 'cybersecurity'],
    # Telecommunications
    'subsector_telecommunications_carrier': [
        'sip_trunks', 'traditional_telecommunications_service', 'naas',
        'data_services', 'lan_management', 'cpaas'],
    'subsector_telecommunications_reseller_agent': [
        'telecom_aggregator', 'sip_trunks', 'crm', 'ccaas',
        'wireless_pots_replacement'],
    # Transportation/Logistics
    'subsector_transportation_logistics_trucking': [
        'crm', 'invoicing_system', 'payroll',
        'physical_security_security_cameras', 'data_services'],
    'subsector_transportation_logistics_courier': [
        'employee_scheduling', 'time_clock', 'invoicing_system', 'crm',
        'payment_processing'],
    'subsector_transportation_logistics_passenger_transport': [
        'employee_scheduling', 'payment_processing',
        'physical_security_security_cameras', 'time_clock', 'web_design'],
    # Utilities
    'subsector_utilities_electric': [
        'contact_center', 'physical_security_security_cameras',
        'data_services', 'energy', 'lan_management'],
    'subsector_utilities_water': [
        'contact_center', 'physical_security_security_cameras',
        'data_services', 'invoicing_system'],
    'subsector_utilities_gas': [
        'contact_center', 'physical_security_security_cameras',
        'data_services', 'energy', 'invoicing_system'],
    # Web Design/Web Hosting
    'subsector_web_design_web_hosting_web_design_agency': [
        'web_design', 'seo', 'graphics_design', 'content_creation',
        'digital_marketing', 'shopping_carts'],
    'subsector_web_design_web_hosting_hosting_provider': [
        'data_services', 'cybersecurity', 'managed_hardware',
        'lan_management', 'custom_software'],
    # Wholesale
    'subsector_wholesale_food_and_beverage_distribution': [
        'crm', 'invoicing_system', 'accounts_payable_automation', 'mobility',
        'waste_garbage_hauling'],
    'subsector_wholesale_general_merchandise': [
        'crm', 'invoicing_system', 'ecommerce', 'ach_services',
        'data_services'],
    # Wholesale Supply
    'subsector_wholesale_supply_restaurant_supply': [
        'crm', 'invoicing_system', 'ecommerce', 'payment_processing',
        'accounts_payable_automation'],
    'subsector_wholesale_supply_building_supply': [
        'crm', 'invoicing_system', 'payment_processing',
        'commercial_construction', 'leasing'],
}


class ResPartnerSubsector(models.Model):
    _inherit = 'res.partner.subsector'

    @api.model
    def _seed_default_technologies(self):
        """Give the seeded sub-sectors a starting Default Tech Stack.

        Only a record whose Default Tech Stack is still empty is touched, so a
        value set up by a user afterwards is never overwritten. A name that is
        not loaded in this database is skipped rather than raising, which keeps
        the call safe on a partially seeded database.
        """
        for xmlid, names in SUBSECTOR_DEFAULTS.items():
            record = self.env.ref(
                'crm_deals.%s' % xmlid, raise_if_not_found=False)
            if not record or record.default_technology_ids:
                continue
            technologies = [
                self.env.ref('crm_deals.tech_%s' % name,
                             raise_if_not_found=False)
                for name in names
            ]
            ids = [tech.id for tech in technologies if tech]
            if ids:
                record.default_technology_ids = [Command.set(ids)]
