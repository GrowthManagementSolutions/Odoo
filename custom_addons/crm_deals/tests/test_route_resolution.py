from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRouteResolution(TransactionCase):
    """Regression cover for the rule lookup and the commission snapshot.

    Both halves of the bug this guards against were real: a rule with empty
    effective dates has to count as always effective, and a line with no start
    date has to fall back to the lead's Default Start Date and then to today.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env['res.partner'].create({
            'name': 'Test Supplier',
            'is_company': True,
            'category_id': [(4, cls.env.ref(
                'crm_deals.partner_category_supplier').id)],
        })
        cls.master = cls.env['res.partner'].create({
            'name': 'Test Master',
            'is_company': True,
            'category_id': [(4, cls.env.ref(
                'crm_deals.partner_category_master_supplier').id)],
        })
        # Open-ended agreement: no date_from, no date_to.
        cls.env['product.master.agreement'].create({
            'master_id': cls.master.id,
            'gms_share': 0.80,
        })
        cls.route = cls.env['product.supplier.route'].create({
            'supplier_id': cls.supplier.id,
            'master_id': cls.master.id,
        })
        cls.direct_route = cls.env['product.supplier.route'].create({
            'supplier_id': cls.supplier.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Test Routed Service',
            'type': 'service',
        })
        # Open-ended rule: no date_from, no date_to.
        cls.rule = cls.env['product.route.rule'].create({
            'route_id': cls.route.id,
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'recurring_basis': 'mrc',
            'residual_rate': 0.30,
            'spiff_multiplier': 6.0,
            'is_default': True,
        })
        cls.lead = cls.env['crm.lead'].create({
            'name': 'Route Resolution Lead',
            'default_start_date': '2026-06-01',
        })

    def _line(self, **vals):
        return self.env['crm.deal.line'].create(dict({
            'lead_id': self.lead.id,
            'product_id': self.product.id,
            'supplier_id': self.supplier.id,
        }, **vals))

    def test_empty_dated_rule_is_always_effective(self):
        """A rule with no date_from or date_to resolves on any date."""
        for date in ('1999-01-01', '2026-06-01', '2099-12-31'):
            self.assertEqual(
                self.route._get_rule(self.product.product_tmpl_id, date),
                self.rule,
                "an open-ended rule must resolve on %s" % date)

    def test_line_without_start_date_falls_back_to_the_lead(self):
        """No start date on the line -> the lead's Default Start Date."""
        line = self._line(start_date=False)
        self.assertEqual(line._route_resolution_date(),
                         self.lead.default_start_date)
        self.assertEqual(line.rule_id, self.rule)
        self.assertEqual(line.residual_rate, 0.30)

    def test_line_without_lead_date_falls_back_to_today(self):
        """No start date and no lead default -> today."""
        self.lead.default_start_date = False
        line = self._line(start_date=False)
        # context_today, not cr.now(): "today" is the user's date, which can
        # differ from the database server's UTC date.
        self.assertEqual(line._route_resolution_date(),
                         fields.Date.context_today(line))
        self.assertEqual(line.rule_id, self.rule)

    def test_snapshot_copies_the_rule_and_the_route_share(self):
        line = self._line(start_date='2026-06-01')
        self.assertEqual(line.route_id, self.route,
                         "the is_default rule's route is the default")
        self.assertEqual(line.rule_id, self.rule)
        self.assertEqual(line.residual_rate, 0.30)
        self.assertEqual(line.gms_share, 0.80, "share comes off the master")
        self.assertAlmostEqual(line.net_rate, 0.24)
        self.assertEqual(line.spiff_multiplier, 6.0)

    def test_share_resolves_without_a_rule(self):
        """The GMS share follows the route even when no rule matches."""
        line = self._line()
        line.route_id = self.direct_route
        self.assertFalse(line.rule_id, "the direct route has no rule")
        self.assertEqual(line.gms_share, 1.0, "a direct route is 100%")
        self.assertEqual(line.residual_rate, 0.0, "no rule, no residual")

    def test_route_is_only_offered_when_a_rule_exists(self):
        other = self.env['product.product'].create({
            'name': 'Unrouted Service', 'type': 'service'})
        line = self._line(product_id=other.id)
        self.assertNotIn(self.route, line.allowed_route_ids)
        self.assertFalse(line.route_id,
                         "a route with no rule for the product is not kept")
