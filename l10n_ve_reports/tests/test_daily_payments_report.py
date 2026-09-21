# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestDailyPaymentsReport(TestAccountReportsCommon):
    """Generic (non-VE) behaviour of the daily payments report handler.

    No `l10n_ve_process_date` field and no retention-journal fields exist on
    a generic-only database, so the handler must rely purely on its
    overridable hooks and never assume a localization field is present.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.handler = cls.env["account.daily.payments.report.handler.oca"]
        cls.report = cls.env.ref("l10n_ve_reports.daily_payments_report")

    def test_validation_date_falls_back_to_move_date(self):
        move = self.init_invoice("out_invoice", amounts=[100.0], post=True)
        self.assertEqual(
            self.handler._get_move_validation_date(move),
            move.date,
        )

    def test_no_journal_excluded_by_default(self):
        self.assertEqual(
            self.handler._get_excluded_journal_ids(self.env.company),
            set(),
        )

        bank_journal = self.company_data["default_journal_bank"]
        cash_journal = self.company_data["default_journal_cash"]
        options = self.report.get_options({})
        journals = self.handler._get_selected_bank_cash_journals(
            self.report, options
        )
        self.assertIn(bank_journal, journals)
        self.assertIn(cash_journal, journals)
