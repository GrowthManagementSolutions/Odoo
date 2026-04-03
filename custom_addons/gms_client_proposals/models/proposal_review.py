from odoo import fields, models


class GmsProposalReview(models.Model):
    _name = "gms.proposal.review"
    _description = "GMS Proposal Review"
    _order = "requested_at desc, id desc"

    proposal_id = fields.Many2one("gms.client.proposal", required=True, ondelete="cascade", index=True)
    requested_by = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    requested_at = fields.Datetime(default=fields.Datetime.now, required=True)
    review_reason = fields.Text(required=True)
    state = fields.Selection([
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ], default="requested", required=True, tracking=True)
    reviewed_by = fields.Many2one("res.users")
    reviewed_at = fields.Datetime()
    notes = fields.Text()
    active = fields.Boolean(default=True)
