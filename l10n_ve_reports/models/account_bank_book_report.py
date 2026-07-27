# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class BankBookReportCustomHandler(models.AbstractModel):
    _name = "account.bank.book.report.handler.oca"
    _inherit = "l10n.ve.liquidity.book.report.mixin"
    _description = "Bank Book Report Custom Handler"

    def _get_journal_types(self):
        return ("bank",)
