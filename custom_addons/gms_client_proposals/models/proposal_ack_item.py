from odoo import fields, models


class GmsClientProposalAckItem(models.Model):
    _name = "gms.client.proposal.ack_item"
    _description = "GMS Client Proposal Acknowledgment Item"
    _order = "display_order, id"

    proposal_id = fields.Many2one("gms.client.proposal", required=True, ondelete="cascade", index=True)
    proposal_line_id = fields.Many2one("gms.client.proposal.line", ondelete="set null")
    source_revision_id = fields.Many2one("gms.client.proposal", ondelete="set null")
    solution_category_id = fields.Many2one(
        "product.product",
        domain=[("x_gms_is_solution_category", "=", True)],
        ondelete="restrict",
    )
    ack_type = fields.Selection([
        ("rejected", "Rejected"),
        ("modified", "Modified"),
        ("removed", "Removed"),
        ("deferred", "Deferred"),
    ], required=True)
    client_facing_text = fields.Text(required=True)
    internal_reason = fields.Text()
    carryforward = fields.Boolean(default=True)
    resolved = fields.Boolean(default=False)
    display_order = fields.Integer(default=10)
    active = fields.Boolean(default=True)
