def migrate(cr, version):
    """Clear lead_type on leads still holding the removed 'prospect' value."""
    cr.execute("UPDATE crm_lead SET lead_type = NULL WHERE lead_type = 'prospect'")
