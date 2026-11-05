from odoo import _, api, fields, models


class ProductRouteRuleCopy(models.TransientModel):
    _name = 'product.route.rule.copy'
    _description = 'Copy Route Rule to Products'

    rule_id = fields.Many2one(
        'product.route.rule',
        string='Rule',
        required=True,
        ondelete='cascade',
    )
    route_id = fields.Many2one(related='rule_id.route_id', readonly=True)
    product_tmpl_ids = fields.Many2many(
        'product.template',
        string='Products',
    )
    # Computed rather than a view domain: "has no rule on this route effective
    # today" cannot be expressed as a leaf on product.template. Same reasoning
    # as config.document's allowed_* fields.
    allowed_product_tmpl_ids = fields.Many2many(
        'product.template',
        relation='product_route_rule_copy_allowed_rel',
        compute='_compute_allowed_product_tmpl_ids',
    )

    @api.depends('rule_id')
    def _compute_allowed_product_tmpl_ids(self):
        today = fields.Date.context_today(self)
        for wizard in self:
            already = self.env['product.route.rule'].search([
                ('route_id', '=', wizard.rule_id.route_id.id),
                '|', ('date_from', '=', False), ('date_from', '<=', today),
                '|', ('date_to', '=', False), ('date_to', '>=', today),
            ]).product_tmpl_id
            wizard.allowed_product_tmpl_ids = self.env['product.template'].search([
                ('id', 'not in', already.ids),
            ])

    def action_copy(self):
        """Clone the rule onto each selected product.

        Every field is copied except is_default: a default belongs to one
        product and supplier, so carrying it across would breach the
        single-default constraint. The rule's own constraints still run on
        each copy, so an overlapping target is refused rather than skipped.
        """
        self.ensure_one()
        created = self.env['product.route.rule']
        for product in self.product_tmpl_ids:
            created |= self.rule_id.copy({
                'product_tmpl_id': product.id,
                'is_default': False,
            })
        return {
            'name': _('Product Rules'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.route.rule',
            'view_mode': 'list,form',
            'domain': [('id', 'in', (self.rule_id | created).ids)],
        }
