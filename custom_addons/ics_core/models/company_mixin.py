from odoo import models


class ICSCompanyMixin(models.AbstractModel):
    _name = "ics.company.mixin"
    _description = "ICS Company Helper"

    def is_ics_company(self, company):
        return (
            company
            and company.name == "INTEGRATED COMPUTER SERVICES INC."
        )