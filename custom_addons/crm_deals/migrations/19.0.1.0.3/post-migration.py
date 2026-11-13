def migrate(cr, version):
    """Copy the old solution_architect_id many2one into the new many2many.

    Odoo leaves the obsolete column in place, so it can still be read here.
    """
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'crm_lead' AND column_name = 'solution_architect_id'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        INSERT INTO crm_lead_solution_architect_rel (lead_id, partner_id)
        SELECT l.id, l.solution_architect_id
          FROM crm_lead l
         WHERE l.solution_architect_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM crm_lead_solution_architect_rel r
                WHERE r.lead_id = l.id AND r.partner_id = l.solution_architect_id
           )
    """)
