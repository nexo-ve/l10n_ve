from odoo import fields
from odoo.tests import tagged

from .common import L10nVePaymentAdvanceCommon


@tagged("post_install", "-at_install")
class TestAdvanceMultiCurrency(L10nVePaymentAdvanceCommon):
    """Advances taken in one currency and shown or applied in another.

    The company books in USD here (``AccountTestInvoicingCommon`` default) and
    ``foreign`` stands in for VES at a flat 40 per unit of company currency, so
    every expected figure below is exact rather than rounding-dependent.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.foreign = cls.setup_other_currency(
            "VES", rates=[("2016-01-01", 40.0)]
        )

    def _create_foreign_advance_line(self, amount=4000.0):
        """Standalone customer advance of ``amount`` in the foreign currency."""
        payment = self.env["account.payment"].create(
            {
                "partner_id": self.customer.id,
                "partner_type": "customer",
                "payment_type": "inbound",
                "amount": amount,
                "currency_id": self.foreign.id,
                "journal_id": self.bank_journal.id,
                "date": fields.Date.context_today(self.env["account.payment"]),
            }
        )
        payment.action_post()
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.customer_advance_account
        )

    def test_foreign_advance_is_converted_into_the_invoice_currency(self):
        # Arrange: 4000 foreign at 40/1 is 100 in company currency
        advance_line = self._create_foreign_advance_line(amount=4000.0)
        invoice = self._create_customer_invoice(amount=500.0)

        # Act
        invoice.invalidate_recordset()
        widget = invoice.invoice_outstanding_advances_widget

        # Assert: the invoice is in company currency, so the advance shows as 100
        amounts = [line["amount"] for line in widget["content"]]
        self.assertEqual(len(amounts), 1)
        self.assertAlmostEqual(amounts[0], 100.0, places=2)
        self.assertEqual(
            widget["content"][0]["currency_id"], invoice.currency_id.id
        )

    def test_advance_in_invoice_currency_is_shown_untouched(self):
        # Arrange: both the advance and the invoice are in the foreign currency
        advance_line = self._create_foreign_advance_line(amount=4000.0)
        invoice = self._create_customer_invoice(amount=20000.0)
        invoice.button_draft()
        invoice.currency_id = self.foreign
        invoice.action_post()

        # Act
        invoice.invalidate_recordset()
        widget = invoice.invoice_outstanding_advances_widget

        # Assert: no conversion, the foreign residual is used as-is
        self.assertEqual(len(widget["content"]), 1)
        self.assertAlmostEqual(widget["content"][0]["amount"], 4000.0, places=2)
        self.assertEqual(advance_line.currency_id, self.foreign)

    def test_wizard_converts_available_advance_into_its_own_currency(self):
        # Arrange
        advance_line = self._create_foreign_advance_line(amount=4000.0)
        invoice = self._create_customer_invoice(amount=500.0)

        # Act
        wizard = self._create_register_wizard(
            invoice,
            amount=100.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )

        # Assert: 4000 foreign surfaced as 100 in the wizard's company currency
        self.assertEqual(wizard.currency_id, invoice.currency_id)
        self.assertAlmostEqual(
            wizard.l10n_ve_advance_amount_available, 100.0, places=2
        )
        self.assertAlmostEqual(
            wizard.l10n_ve_invoice_amount_residual, 500.0, places=2
        )

    def test_applying_a_foreign_advance_reduces_the_invoice_residual(self):
        # Arrange
        advance_line = self._create_foreign_advance_line(amount=4000.0)
        invoice = self._create_customer_invoice(amount=500.0)

        # Act: apply the whole 100 company-currency equivalent
        self._create_register_wizard(
            invoice,
            amount=100.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )._create_payments()

        # Assert
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 400.0, places=2)
        advance_line.invalidate_recordset()
        self.assertTrue(advance_line.reconciled)
