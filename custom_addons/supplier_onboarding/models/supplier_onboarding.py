from odoo import fields, models, _
from odoo.exceptions import UserError


class SupplierOnboarding(models.Model):
    _name = "supplier.onboarding"
    _description = "Supplier Onboarding"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "legal_business_name"
    _order = "create_date desc"

    legal_business_name = fields.Char(required=True, tracking=True)
    dba_name = fields.Char(string="DBA", tracking=True)

    street = fields.Char()
    street2 = fields.Char()
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string="State")
    zip = fields.Char(string="ZIP")
    country_id = fields.Many2one("res.country", string="Country")

    website = fields.Char()
    product_services_offered = fields.Text(string="Products / Services Offered")

    channel_manager_id = fields.Many2one(
        "res.users",
        string="Channel Manager",
        tracking=True,
        default=lambda self: self.env.user,
    )
    channel_manager_email = fields.Char()
    channel_manager_phone = fields.Char()

    contact_name = fields.Char(required=True)
    contact_email = fields.Char(required=True)
    contact_phone = fields.Char()

    supplier_contract = fields.Binary(string="Supplier Contract")
    supplier_contract_filename = fields.Char()

    supplier_partner_id = fields.Many2one(
        "res.partner",
        string="Supplier Contact",
        readonly=True,
        copy=False,
    )

    nda_sent = fields.Boolean(default=False, readonly=True, copy=False)
    nda_sent_date = fields.Datetime(readonly=True, copy=False)

    state = fields.Selection([
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("nda_sent", "NDA Sent"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ], default="draft", tracking=True)

    notes = fields.Text()

    def action_submit(self):
        for rec in self:
            if not rec.contact_email:
                raise UserError(_("Contact Email is required before submission."))
            rec.state = "submitted"

    def action_send_nda(self):
        template = self.env.ref(
            "supplier_onboarding.email_template_supplier_nda",
            raise_if_not_found=False,
        )

        for rec in self:
            if not rec.contact_email:
                raise UserError(_("Cannot send NDA because Contact Email is missing."))

            if template:
                template.send_mail(rec.id, force_send=True)

            rec.write({
                "nda_sent": True,
                "nda_sent_date": fields.Datetime.now(),
                "state": "nda_sent",
            })

    def action_approve(self):
        for rec in self:
            partner = False

            if rec.supplier_partner_id:
                partner = rec.supplier_partner_id
            elif rec.contact_email:
                partner = self.env["res.partner"].search([
                    ("email", "=", rec.contact_email)
                ], limit=1)

            vals = {
                "name": rec.legal_business_name,
                "email": rec.contact_email,
                "phone": rec.contact_phone,
                "website": rec.website,
                "street": rec.street,
                "street2": rec.street2,
                "city": rec.city,
                "state_id": rec.state_id.id or False,
                "zip": rec.zip,
                "country_id": rec.country_id.id or False,
                "x_gms_is_supplier": True,
                "x_gms_active_for_proposals": True,
                "x_gms_partner_type": "supplier",
            }

            if partner:
                partner.write(vals)
            else:
                partner = self.env["res.partner"].create(vals)

            rec.write({
                "state": "approved",
                "supplier_partner_id": partner.id,
            })

    def action_reject(self):
        self.write({"state": "rejected"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})