from odoo import _, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    config_document_count = fields.Integer(
        string='Config Documents',
        compute='_compute_config_document_count',
    )

    def _compute_config_document_count(self):
        data = self.env['config.document']._read_group(
            [('task_id', 'in', self.ids)],
            groupby=['task_id'],
            aggregates=['__count'],
        )
        mapped = {task.id: count for task, count in data}
        for task in self:
            task.config_document_count = mapped.get(task.id, 0)

    def action_view_config_documents(self):
        self.ensure_one()
        return {
            'name': _('Config Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'config.document',
            'view_mode': 'list,kanban,form',
            'domain': [('task_id', '=', self.id)],
            'context': {'default_task_id': self.id},
        }

    def action_add_config_document(self):
        self.ensure_one()
        # The deal line that generated this task (#17), when there is one.
        deal = self.env['crm.deal.line'].search([('task_id', '=', self.id)], limit=1)
        company = self.partner_id.commercial_partner_id or self.partner_id
        return self.env['config.document']._prefill_action({
            'task_id': self.id,
            'partner_id': company.id,
            'deal_line_id': deal.id,
        })
