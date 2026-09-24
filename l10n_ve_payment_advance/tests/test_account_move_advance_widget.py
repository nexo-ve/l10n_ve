from odoo.tests import tagged

from .common import L10nVePaymentAdvanceCommon


@tagged("post_install", "-at_install")
class TestAccountMoveAdvanceWidget(L10nVePaymentAdvanceCommon):
    def test_widget_lists_open_advance_line_for_same_partner(self):
        # Arrange: a standalone payment with no invoice lines becomes an advance
        payment = self._create_standalone_payment(
            self.customer, "customer", "inbound", amount=500.0
        )
        advance_line = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.customer_advance_account
        )
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act
        widget = invoice.invoice_outstanding_advances_widget

        # Assert
        self.assertTrue(invoice.invoice_has_outstanding_advances)
        widget_ids = [entry["id"] for entry in widget["content"]]
        self.assertIn(advance_line.id, widget_ids)

    def test_widget_not_shown_for_draft_invoice(self):
        # Arrange
        invoice = self._create_customer_invoice(amount=1000.0, post=False)

        # Assert
        self.assertFalse(invoice.invoice_show_advances_widget)

    def test_widget_not_shown_for_paid_invoice(self):
        # Arrange
        invoice = self._create_customer_invoice(amount=200.0)
        wizard = self._create_register_wizard(invoice, amount=200.0)
        wizard._create_payments()
        invoice.invalidate_recordset()

        # Assert
        self.assertEqual(invoice.payment_state, "paid")
        self.assertFalse(invoice.invoice_show_advances_widget)

    def test_action_open_advance_apply_register_returns_act_window(self):
        # Arrange
        payment = self._create_standalone_payment(
            self.customer, "customer", "inbound", amount=500.0
        )
        advance_line = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.customer_advance_account
        )
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act
        action = invoice.action_open_advance_apply_register(advance_line.id)

        # Assert
        self.assertEqual(action["res_model"], "account.payment.register")
        self.assertEqual(action["context"]["l10n_ve_apply_advance"], True)
        self.assertEqual(
            action["context"]["default_l10n_ve_advance_line_id"], advance_line.id
        )

    def test_action_open_advance_apply_register_returns_false_for_missing_line(self):
        # Arrange
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act
        action = invoice.action_open_advance_apply_register(999999999)

        # Assert
        self.assertFalse(action)
