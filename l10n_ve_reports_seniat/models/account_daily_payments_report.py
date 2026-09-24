# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class DailyPaymentsReportCustomHandler(models.AbstractModel):
    _inherit = "account.daily.payments.report.handler.oca"

    def _get_move_validation_date(self, move):
        if move.l10n_ve_process_date:
            return move.l10n_ve_process_date
        payment = self._get_move_payment(move)
        if payment and payment.l10n_ve_process_date:
            return payment.l10n_ve_process_date
        return super()._get_move_validation_date(move)

    def _get_excluded_journal_ids(self, companies):
        retention_fields = (
            "iva_supplier_retention_journal_id",
            "iva_customer_retention_journal_id",
            "islr_supplier_retention_journal_id",
            "islr_customer_retention_journal_id",
            "municipal_supplier_retention_journal_id",
            "municipal_customer_retention_journal_id",
        )
        excluded = set(super()._get_excluded_journal_ids(companies))
        for field_name in retention_fields:
            excluded |= set(companies.mapped(field_name).ids)
        return excluded
