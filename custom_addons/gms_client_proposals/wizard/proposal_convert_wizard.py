from odoo import fields, models
from odoo.exceptions import UserError


class GmsProposalConvertWizard(models.TransientModel):
    _name = "gms.proposal.convert.wizard"
    _description = "Convert Proposal to Customer Setup"

    proposal_id = fields.Many2one("gms.client.proposal", required=True)
    partner_id = fields.Many2one("res.partner", required=True)
    create_customer_account = fields.Boolean(default=True)
    create_merchant_accounts = fields.Boolean(default=True)
    create_supplier_services = fields.Boolean(default=True)
    seed_forecast = fields.Boolean(default=True)
    customer_account_id = fields.Many2one("gms.customer.account", readonly=True)
    notes = fields.Text()

    def action_convert(self):
        self.ensure_one()
        proposal = self.proposal_id

        if proposal.state != "accepted":
            raise UserError("Only accepted proposals can be converted.")

        customer = False
        if self.create_customer_account:
            customer = self.env["gms.customer.account"].create({
                "name": proposal.partner_id.name or proposal.name,
                "partner_id": proposal.partner_id.id,
                "crm_lead_id": proposal.crm_lead_id.id,
                "source_proposal_id": proposal.id,
                "primary_rep_id": proposal.assigned_rep_id.id,
                "support_manager_id": proposal.support_manager_id.id,
                "channel_manager_id": proposal.channel_manager_id.id,
                "state": "draft",
            })
            self.customer_account_id = customer.id

        merchant_map = {}
        if self.create_merchant_accounts and customer:
            for merchant_line in proposal.merchant_ids:
                merchant = self.env["gms.merchant.account"].create({
                    "name": merchant_line.name,
                    "customer_account_id": customer.id,
                    "source_proposal_merchant_id": merchant_line.id,
                    "legal_name": merchant_line.legal_name,
                    "dba_name": merchant_line.dba_name,
                    "street": merchant_line.street,
                    "street2": merchant_line.street2,
                    "city": merchant_line.city,
                    "state_id": merchant_line.state_id.id,
                    "zip": merchant_line.zip,
                    "country_id": merchant_line.country_id.id,
                    "state": "draft",
                })
                merchant_map[merchant_line.id] = merchant

        if self.create_supplier_services:
            for line in proposal.line_ids:
                merchant = merchant_map.get(line.proposal_merchant_id.id)
                if not merchant:
                    continue

                service = self.env["gms.supplier.service"].create({
                    "merchant_account_id": merchant.id,
                    "supplier_id": line.supplier_id.id,
                    "product_id": line.product_id.id,
                    "source_proposal_line_id": line.id,
                    "state": "draft",
                    "expected_monthly_fee": line.monthly_recurring_fee,
                    "expected_one_time_fee": line.one_time_fee,
                    "expected_contract_term_months": line.contract_term_months,
                    "currency_id": proposal.currency_id.id,
                })

                if self.seed_forecast and customer:
                    self.env["gms.forecast.record"].create({
                        "customer_account_id": customer.id,
                        "merchant_account_id": merchant.id,
                        "supplier_service_id": service.id,
                        "period_month": fields.Date.today().replace(day=1),
                        "forecast_source": "accepted_proposal",
                        "expected_recurring_amount": line.monthly_recurring_fee,
                        "expected_one_time_amount": line.one_time_fee,
                        "expected_contract_term_months": line.contract_term_months,
                        "source_proposal_id": proposal.id,
                        "source_proposal_line_id": line.id,
                        "currency_id": proposal.currency_id.id,
                    })

        proposal.write({
            "converted_to_customer": True,
            "converted_on": fields.Datetime.now(),
            "converted_by": self.env.user.id,
        })

        return {"type": "ir.actions.act_window_close"}