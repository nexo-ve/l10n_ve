from odoo.tests import tagged

from .common import L10nVePaymentAdvanceCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentRegisterOverpayment(L10nVePaymentAdvanceCommon):
    def test_overpayment_kept_as_advance_creates_writeoff_and_pays_invoice(self):
        # Arrange
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act: register a payment larger than the residual
        wizard = self._create_register_wizard(invoice, amount=1500.0)
        self.assertEqual(wizard.payment_difference_handling, "advance")
        payment = wizard._create_payments()

        # Assert: the excess is written off to the customer advance account
        writeoff_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.customer_advance_account
        )
        self.assertTrue(writeoff_lines)
        self.assertAlmostEqual(
            abs(sum(writeoff_lines.mapped("balance"))), 500.0, places=2
        )

        invoice.invalidate_recordset()
        self.assertEqual(invoice.payment_state, "paid")
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)

    def test_show_advance_difference_handling_true_for_customer_overpayment(self):
        # Arrange
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act
        wizard = self._create_register_wizard(invoice, amount=1500.0)

        # Assert
        self.assertLess(wizard.payment_difference, 0.0)
        self.assertTrue(wizard.show_advance_difference_handling)

    def test_show_advance_difference_handling_true_for_supplier_overpayment(self):
        # Arrange
        bill = self._create_vendor_bill(amount=1000.0)

        # Act
        wizard = self._create_register_wizard(bill, amount=1500.0)

        # Assert
        self.assertLess(wizard.payment_difference, 0.0)
        self.assertTrue(wizard.show_advance_difference_handling)

    def test_show_advance_difference_handling_false_for_underpayment(self):
        # Arrange
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act: register a partial payment (short of the residual)
        wizard = self._create_register_wizard(invoice, amount=400.0)

        # Assert
        self.assertGreater(wizard.payment_difference, 0.0)
        self.assertFalse(wizard.show_advance_difference_handling)

    def test_show_advance_difference_handling_false_without_advance_account(self):
        # Arrange: remove the company advance account configuration
        self.company.account_customer_advance_id = False
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act
        wizard = self._create_register_wizard(invoice, amount=1500.0)

        # Assert
        self.assertFalse(wizard.show_advance_difference_handling)
