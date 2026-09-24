from odoo.tests import tagged

from .common import L10nVePaymentAdvanceCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentAdvance(L10nVePaymentAdvanceCommon):
    def test_standalone_inbound_customer_payment_posts_to_advance_account(self):
        # Arrange / Act: a customer payment with no invoice lines behind it
        payment = self._create_standalone_payment(
            self.customer, "customer", "inbound", amount=500.0
        )

        # Assert
        self.assertFalse(payment.payment_has_invoice_lines)
        self.assertEqual(payment.destination_account_id, self.customer_advance_account)

    def test_standalone_outbound_supplier_payment_posts_to_advance_account(self):
        # Arrange / Act: a supplier payment with no bill lines behind it
        payment = self._create_standalone_payment(
            self.supplier, "supplier", "outbound", amount=500.0
        )

        # Assert
        self.assertFalse(payment.payment_has_invoice_lines)
        self.assertEqual(payment.destination_account_id, self.supplier_advance_account)

    def test_payment_from_wizard_against_invoice_keeps_receivable_destination(self):
        # Arrange
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act
        wizard = self._create_register_wizard(invoice, amount=1000.0)
        payments = wizard._create_payments()

        # Assert
        self.assertTrue(payments.payment_has_invoice_lines)
        self.assertEqual(
            payments.destination_account_id,
            self.company_data["default_account_receivable"],
        )
        self.assertNotEqual(
            payments.destination_account_id, self.customer_advance_account
        )

    def test_payment_from_wizard_against_bill_keeps_payable_destination(self):
        # Arrange
        bill = self._create_vendor_bill(amount=1000.0)

        # Act
        wizard = self._create_register_wizard(bill, amount=1000.0)
        payments = wizard._create_payments()

        # Assert
        self.assertTrue(payments.payment_has_invoice_lines)
        self.assertEqual(
            payments.destination_account_id,
            self.company_data["default_account_payable"],
        )
        self.assertNotEqual(
            payments.destination_account_id, self.supplier_advance_account
        )
