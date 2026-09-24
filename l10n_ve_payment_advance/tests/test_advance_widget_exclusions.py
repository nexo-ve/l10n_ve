from odoo import Command
from odoo.tests import tagged

from .common import L10nVePaymentAdvanceCommon


@tagged("post_install", "-at_install")
class TestAdvanceWidgetExclusions(L10nVePaymentAdvanceCommon):
    """Lines the invoice advances widget must NOT offer.

    ``_get_outstanding_advance_lines`` keeps a line only when it passes both
    ``_is_open_advance_line`` and ``_line_belongs_to_invoice_partner``. The
    happy path is covered elsewhere; these tests exercise the rejections, so
    that loosening either predicate fails the suite instead of silently
    offering the wrong money.
    """

    def _advance_line_of(self, payment):
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id
            in (self.customer_advance_account | self.supplier_advance_account)
        )

    def _widget_line_ids(self, invoice):
        invoice.invalidate_recordset()
        widget = invoice.invoice_outstanding_advances_widget or {}
        return [entry["id"] for entry in widget.get("content", [])]

    def _valid_advance_line(self, amount=100.0):
        """A legitimate advance for self.customer, used as a positive control.

        Every exclusion test asserts this line IS offered, so an assertNotIn
        cannot pass just because the widget came back empty.
        """
        payment = self._create_standalone_payment(
            self.customer, "customer", "inbound", amount=amount
        )
        return self._advance_line_of(payment)

    def test_widget_excludes_advance_of_another_partner(self):
        # Arrange
        other_customer = self.env["res.partner"].create({"name": "Unrelated Customer"})
        other_payment = self._create_standalone_payment(
            other_customer, "customer", "inbound", amount=500.0
        )
        other_line = self._advance_line_of(other_payment)
        control_line = self._valid_advance_line()
        invoice = self._create_customer_invoice(amount=1000.0)

        # Assert
        widget_ids = self._widget_line_ids(invoice)
        self.assertIn(control_line.id, widget_ids)
        self.assertNotIn(other_line.id, widget_ids)

    def test_widget_excludes_line_on_a_different_account(self):
        # Arrange: same partner, same shape, but not the configured account
        other_account = self.env["account.account"].create(
            {
                "name": "Unconfigured Liability Widget Test",
                "code": "210904",
                "account_type": "liability_current",
                "reconcile": True,
                "company_ids": [Command.set([self.company.id])],
            }
        )
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "partner_id": self.customer.id,
                "line_ids": [
                    Command.create(
                        {
                            "name": "Not an advance",
                            "account_id": other_account.id,
                            "partner_id": self.customer.id,
                            "credit": 500.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Balancing line",
                            "account_id": self.company_data[
                                "default_account_receivable"
                            ].id,
                            "partner_id": self.customer.id,
                            "debit": 500.0,
                        }
                    ),
                ],
            }
        )
        entry.action_post()
        stray_line = entry.line_ids.filtered(
            lambda line: line.account_id == other_account
        )
        control_line = self._valid_advance_line()
        invoice = self._create_customer_invoice(amount=1000.0)

        # Assert
        widget_ids = self._widget_line_ids(invoice)
        self.assertIn(control_line.id, widget_ids)
        self.assertNotIn(stray_line.id, widget_ids)

    def test_widget_excludes_a_supplier_advance_on_a_customer_invoice(self):
        # Arrange: right company, wrong side of the ledger
        supplier_payment = self._create_standalone_payment(
            self.supplier, "supplier", "outbound", amount=500.0
        )
        supplier_line = self._advance_line_of(supplier_payment)
        control_line = self._valid_advance_line()
        invoice = self._create_customer_invoice(amount=1000.0)

        # Assert
        widget_ids = self._widget_line_ids(invoice)
        self.assertIn(control_line.id, widget_ids)
        self.assertNotIn(supplier_line.id, widget_ids)

    def test_widget_excludes_an_already_consumed_advance(self):
        # Arrange: a 500 advance fully applied to a first invoice
        payment = self._create_standalone_payment(
            self.customer, "customer", "inbound", amount=500.0
        )
        advance_line = self._advance_line_of(payment)
        first_invoice = self._create_customer_invoice(amount=1000.0)
        self._create_register_wizard(
            first_invoice,
            amount=500.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )._create_payments()

        # Act: a later invoice should not be offered the spent advance
        control_line = self._valid_advance_line()
        second_invoice = self._create_customer_invoice(amount=1000.0)

        # Assert
        advance_line.invalidate_recordset()
        self.assertTrue(advance_line.reconciled)
        widget_ids = self._widget_line_ids(second_invoice)
        self.assertIn(control_line.id, widget_ids)
        self.assertNotIn(advance_line.id, widget_ids)
