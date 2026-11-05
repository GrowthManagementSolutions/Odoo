from odoo import models


class CrmQuotationPartner(models.TransientModel):
    """Reuse sale_crm's New Quotation customer wizard for "Create Contact".

    With ``contact_only`` in the context the dialog performs only the partner
    assignment and returns to the lead, skipping the quotation step. Without the
    flag the standard New Quotation behaviour is untouched.
    """
    _inherit = 'crm.quotation.partner'

    def action_apply(self):
        if not self.env.context.get('contact_only'):
            return super().action_apply()
        self.ensure_one()
        # Same branches as core's action_apply, delegating the actual work to the
        # same crm.lead method; only the closing action_new_quotation() differs.
        if self.action == 'create':
            self.lead_id._handle_partner_assignment(create_missing=True)
        elif self.action == 'exist':
            self.lead_id._handle_partner_assignment(
                force_partner_id=self.partner_id.id, create_missing=False)
        # 'nothing' assigns no customer, as in core.
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'res_id': self.lead_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
