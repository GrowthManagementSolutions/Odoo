from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductMasterAgreement(models.Model):
    _name = 'product.master.agreement'
    _description = 'Master Supplier Agreement'
    _order = 'master_id, date_from desc, id'

    master_id = fields.Many2one(
        'res.partner',
        string='Master Supplier',
        required=True,
        ondelete='cascade',
        index=True,
        domain=lambda self: self.env['res.partner']._domain_tagged(
            'crm_deals.partner_category_master_supplier'),
    )
    # Stored as a fraction (0.85), rendered by the percentage widget as 85%.
    # Every rate in #53 follows that convention.
    gms_share = fields.Float(
        string='GMS Share',
        digits=(16, 6),
        required=True,
        help="Share of the residual the master supplier passes on to GMS.",
    )
    # Both dates are optional: an empty date_from means effective from the
    # beginning, an empty date_to means no end.
    date_from = fields.Date(string='Effective From')
    date_to = fields.Date(string='Effective To')
    notes = fields.Text(string='Notes')

    @api.depends('master_id', 'date_from', 'date_to')
    def _compute_display_name(self):
        for agreement in self:
            agreement.display_name = '%s - %s' % (
                agreement.master_id.name or '',
                agreement.date_from or '',
            )

    @api.constrains('gms_share')
    def _check_gms_share(self):
        for agreement in self:
            if not 0 <= agreement.gms_share <= 1:
                raise ValidationError(_(
                    "GMS Share must be between 0% and 100%."))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for agreement in self:
            if agreement.date_to and agreement.date_from \
                    and agreement.date_to < agreement.date_from:
                raise ValidationError(_(
                    "Effective To cannot be earlier than Effective From."))

    @api.constrains('master_id', 'date_from', 'date_to')
    def _check_no_overlap(self):
        """One effective agreement per master supplier at any given date.

        Two ranges overlap unless one ends before the other starts; an empty
        date_to means open-ended, so it overlaps everything after date_from.
        """
        for agreement in self:
            others = self.search([
                ('id', '!=', agreement.id),
                ('master_id', '=', agreement.master_id.id),
            ])
            for other in others:
                # An empty end runs on forever and an empty start reaches back
                # forever, so a miss needs both compared dates to be set.
                starts_after = (other.date_to and agreement.date_from
                                and agreement.date_from > other.date_to)
                ends_before = (agreement.date_to and other.date_from
                               and agreement.date_to < other.date_from)
                if not starts_after and not ends_before:
                    raise ValidationError(_(
                        "%(master)s already has an agreement covering these "
                        "dates (from %(other_from)s).",
                        master=agreement.master_id.name,
                        other_from=other.date_from,
                    ))
