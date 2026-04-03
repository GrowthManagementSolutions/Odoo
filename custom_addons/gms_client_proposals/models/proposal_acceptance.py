from odoo import fields, models


class GmsProposalAcceptance(models.Model):
    _name = "gms.proposal.acceptance"
    _description = "GMS Proposal Acceptance"
    _order = "accepted_date desc, id desc"

    proposal_id = fields.Many2one("gms.client.proposal", required=True, ondelete="cascade", index=True)
    accepted_by_name = fields.Char()
    accepted_title = fields.Char()
    accepted_date = fields.Date()
    signature_placeholder = fields.Boolean(default=True)
    ack_initials_placeholder = fields.Boolean(default=True)
    #sign_request_id = fields.Many2one("sign.request", copy=False)
    #signed_attachment_id = fields.Many2one("ir.attachment", copy=False)
    acceptance_method = fields.Selection([
        ("manual", "Manual"),
        ("pdf", "PDF"),
        ("sign", "Odoo Sign"),
    ], default="manual")
