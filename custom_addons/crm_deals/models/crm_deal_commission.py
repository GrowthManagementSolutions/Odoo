from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

PERIOD_MONTHS = {'monthly': 1, 'quarterly': 3, 'annual': 12}


class CrmDealCommission(models.Model):
    _name = 'crm.deal.commission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Deal Commission'
    _order = 'due_date, id'
    _rec_names_search = ['deal_line_id.deal_ref', 'product_id.name']

    deal_line_id = fields.Many2one(
        'crm.deal.line', string='Deal', required=True,
        ondelete='cascade', index=True)
    lead_id = fields.Many2one(
        related='deal_line_id.lead_id', string='Opportunity', store=True, index=True)
    partner_id = fields.Many2one(
        related='deal_line_id.partner_id', string='Customer', store=True)
    product_id = fields.Many2one(
        related='deal_line_id.product_id', string='Product', store=True)
    payer_id = fields.Many2one('res.partner', string='Payer', index=True)
    commission_type = fields.Selection(
        selection=[('recurring', 'Recurring'), ('one_time', 'One-Time')],
        string='Type', required=True)
    due_date = fields.Date(string='Due Date', required=True, index=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.ref('base.USD'))
    expected_amount = fields.Monetary(
        string='Expected', currency_field='currency_id')
    received_amount = fields.Monetary(
        string='Received', currency_field='currency_id', tracking=True)
    received_date = fields.Date(string='Received Date', tracking=True)
    status = fields.Selection(
        selection=[('pending', 'Pending'), ('received', 'Received'),
                   ('cancelled', 'Cancelled')],
        string='Status', default='pending', required=True, tracking=True)
    is_overdue = fields.Boolean(
        string='Overdue', compute='_compute_is_overdue', store=True)
    notes = fields.Text(string='Notes')

    @api.depends('deal_line_id.deal_ref', 'due_date')
    def _compute_display_name(self):
        for commission in self:
            ref = commission.deal_line_id.deal_ref or _("Draft")
            commission.display_name = '%s - %s' % (ref, commission.due_date or '')

    @api.depends('status', 'due_date')
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for commission in self:
            commission.is_overdue = bool(
                commission.status == 'pending'
                and commission.due_date and commission.due_date < today)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_received(self):
        """Pending and cancelled rows may be deleted by hand; received ones
        carry a payment and must be set back to Pending first (#56)."""
        received = self.filtered(lambda c: c.status == 'received')
        if received:
            raise UserError(_(
                "These commission rows have been received and cannot be "
                "deleted: %(rows)s.\n\nSet them back to Pending first if the "
                "payment was recorded in error.",
                rows=", ".join(received.mapped('display_name')),
            ))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_mark_received(self):
        today = fields.Date.context_today(self)
        for commission in self.filtered(lambda c: c.status == 'pending'):
            commission.write({
                'status': 'received',
                'received_date': commission.received_date or today,
                'received_amount': commission.received_amount or commission.expected_amount,
            })
        return True

    def action_mark_pending(self):
        self.filtered(lambda c: c.status == 'received').write({
            'status': 'pending',
            'received_date': False,
            'received_amount': 0.0,
        })
        return True

    # ------------------------------------------------------------------
    # Daily maintenance
    # ------------------------------------------------------------------
    @api.model
    def _cron_commission_maintenance(self):
        """Refresh overdue flags, extend month-to-month schedules, and chase."""
        today = fields.Date.context_today(self)
        # Lines that are about to flip to overdue (before recomputation).
        newly_overdue = self.search([
            ('status', '=', 'pending'),
            ('due_date', '<', today),
            ('is_overdue', '=', False),
        ])
        # is_overdue is stored+computed: force a recompute rather than writing it.
        self.env.add_to_compute(self._fields['is_overdue'], self.search([]))
        self.env.flush_all()

        # Keep month-to-month deals 12 months ahead. Only rows after each
        # line's latest existing one are added, so deleted rows stay deleted.
        rolling = self.env['crm.deal.line'].search([
            ('status', '=', 'accepted'),
            ('contract_term', '=', 'month_to_month'),
            ('start_date', '!=', False),
            ('forecast_generated', '=', True),
        ])
        rolling._extend_month_to_month()

        # Chase the newly overdue ones.
        for commission in newly_overdue:
            user = commission.lead_id.user_id
            if not user:
                continue
            commission.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Follow up with %s", commission.payer_id.display_name or ''),
                user_id=user.id,
            )
        return True
