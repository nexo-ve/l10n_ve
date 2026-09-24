# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestDailyPaymentsSeniat(L10nVeSeniatCommon):
    """VE override of the daily payments report hooks: process date wins
    over move/payment date, and the six company retention journals are
    excluded from the report.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.handler = cls.env["account.daily.payments.report.handler.oca"]

    def test_process_date_wins(self):
        move = self._l10n_ve_create_invoice(post=True)
        process_date = date(2024, 1, 15)
        move.l10n_ve_process_date = process_date
        self.assertEqual(
            self.handler._get_move_validation_date(move),
            process_date,
        )

        # Without a process date, falls back to the generic behaviour (move date).
        move.l10n_ve_process_date = False
        self.assertEqual(
            self.handler._get_move_validation_date(move),
            move.date,
        )

    def test_retention_journals_excluded(self):
        retention_fields = (
            "iva_supplier_retention_journal_id",
            "iva_customer_retention_journal_id",
            "islr_supplier_retention_journal_id",
            "islr_customer_retention_journal_id",
            "municipal_supplier_retention_journal_id",
            "municipal_customer_retention_journal_id",
        )
        company = self.env.company
        retention_journals = self.env["account.journal"]
        for field_name in retention_fields:
            journal = self.env["account.journal"].create(
                {
                    "name": f"Retention journal {field_name}",
                    "type": "cash",
                    "company_id": company.id,
                }
            )
            company[field_name] = journal
            retention_journals |= journal

        excluded = self.handler._get_excluded_journal_ids(company)
        self.assertEqual(excluded, set(retention_journals.ids))
