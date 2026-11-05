from odoo import _, fields, models


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    config_document_count = fields.Integer(
        string='Config Documents',
        compute='_compute_config_document_count',
    )

    def _compute_config_document_count(self):
        data = self.env['config.document']._read_group(
            [('ticket_id', 'in', self.ids)],
            groupby=['ticket_id'],
            aggregates=['__count'],
        )
        mapped = {ticket.id: count for ticket, count in data}
        for ticket in self:
            ticket.config_document_count = mapped.get(ticket.id, 0)

    def action_view_config_documents(self):
        self.ensure_one()
        return {
            'name': _('Config Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'config.document',
            'view_mode': 'list,kanban,form',
            'domain': [('ticket_id', '=', self.id)],
            'context': {'default_ticket_id': self.id},
        }

    def action_add_config_document(self):
        self.ensure_one()
        company = self.partner_id.commercial_partner_id or self.partner_id
        return self.env['config.document']._prefill_action({
            'ticket_id': self.id,
            'partner_id': company.id,
        })
