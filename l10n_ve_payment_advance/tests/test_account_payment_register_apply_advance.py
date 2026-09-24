from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import L10nVePaymentAdvanceCommon


@tagged("post_install", "-at_install")
class TestAccountPaymentRegisterApplyAdvance(L10nVePaymentAdvanceCommon):
    def _create_open_advance_line(self, partner=None, amount=500.0):
        payment = self._create_standalone_payment(
            partner or self.customer, "customer", "inbound", amount=amount
        )
        return payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.customer_advance_account
        )

    def _create_line_on_unconfigured_account(self, partner=None, amount=500.0):
        """Open credit line for the SAME partner on a non-advance account.

        Isolates the account check from the partner check: the only thing wrong
        with this line is which account it sits on.
        """
        partner = partner or self.customer
        other_account = self.env["account.account"].create(
            {
                "name": "Unconfigured Liability Test",
                "code": "210903",
                "account_type": "liability_current",
                "reconcile": True,
                "company_ids": [Command.set([self.company.id])],
            }
        )
        entry = self.env["account.move"].create(
            {
                "move_type": "entry",
                "partner_id": partner.id,
                "line_ids": [
                    Command.create(
                        {
                            "name": "Not an advance",
                            "account_id": other_account.id,
                            "partner_id": partner.id,
                            "credit": amount,
                            "debit": 0.0,
                        }
                    ),
                    Command.create(
                        {
                            "name": "Balancing line",
                            "account_id": self.company_data[
                                "default_account_receivable"
                            ].id,
                            "partner_id": partner.id,
                            "debit": amount,
                            "credit": 0.0,
                        }
                    ),
                ],
            }
        )
        entry.action_post()
        return entry.line_ids.filtered(lambda line: line.account_id == other_account)

    def test_applying_advance_reconciles_against_invoice(self):
        # Arrange
        advance_line = self._create_open_advance_line(amount=500.0)
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act
        wizard = self._create_register_wizard(
            invoice,
            amount=500.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )
        wizard._create_payments()

        # Assert
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 500.0, places=2)
        advance_line.invalidate_recordset()
        self.assertTrue(advance_line.reconciled)

    def test_advance_smaller_than_invoice_is_consumed_in_full(self):
        # Arrange: the advance covers less than the invoice residual
        advance_line = self._create_open_advance_line(amount=300.0)
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act: apply the whole advance, leaving the invoice partially paid
        wizard = self._create_register_wizard(
            invoice,
            amount=300.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )
        wizard._create_payments()

        # Assert
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 700.0, places=2)
        advance_line.invalidate_recordset()
        self.assertTrue(advance_line.reconciled)

    def test_applying_part_of_an_advance_leaves_the_rest_available(self):
        # Arrange: a 500 advance against a 1000 invoice, but only 200 is applied
        advance_line = self._create_open_advance_line(amount=500.0)
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act
        wizard = self._create_register_wizard(
            invoice,
            amount=200.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )
        wizard._create_payments()

        # Assert: the invoice drops by the applied amount only...
        invoice.invalidate_recordset()
        self.assertAlmostEqual(invoice.amount_residual, 800.0, places=2)

        # ...and the advance line stays open with the remaining 300 available
        advance_line.invalidate_recordset()
        self.assertFalse(advance_line.reconciled)
        self.assertAlmostEqual(abs(advance_line.amount_residual), 300.0, places=2)

    def test_remaining_advance_can_be_applied_to_a_second_invoice(self):
        # Arrange: consume 200 of a 500 advance on a first invoice
        advance_line = self._create_open_advance_line(amount=500.0)
        first_invoice = self._create_customer_invoice(amount=1000.0)
        self._create_register_wizard(
            first_invoice,
            amount=200.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )._create_payments()

        # Act: apply the remaining 300 to a second invoice
        second_invoice = self._create_customer_invoice(amount=400.0)
        self._create_register_wizard(
            second_invoice,
            amount=300.0,
            l10n_ve_apply_advance=True,
            l10n_ve_advance_line_id=advance_line.id,
        )._create_payments()

        # Assert
        second_invoice.invalidate_recordset()
        self.assertAlmostEqual(second_invoice.amount_residual, 100.0, places=2)
        advance_line.invalidate_recordset()
        self.assertTrue(advance_line.reconciled)

    def test_apply_advance_requires_an_advance_line(self):
        # Arrange
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act / Assert
        with self.assertRaisesRegex(UserError, "Seleccione la línea de anticipo"):
            self._create_register_wizard(
                invoice,
                amount=100.0,
                l10n_ve_apply_advance=True,
            )

    def test_apply_advance_rejects_line_from_a_different_partner(self):
        # Arrange: same advance account, different partner
        other_customer = self.env["res.partner"].create({"name": "Other Customer"})
        advance_line = self._create_open_advance_line(
            partner=other_customer, amount=500.0
        )
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act / Assert
        with self.assertRaisesRegex(UserError, "no corresponde al cliente"):
            self._create_register_wizard(
                invoice,
                amount=100.0,
                l10n_ve_apply_advance=True,
                l10n_ve_advance_line_id=advance_line.id,
            )

    def test_apply_advance_rejects_line_from_a_different_account(self):
        # Arrange: right partner, wrong account — so only the account check can fire
        wrong_account_line = self._create_line_on_unconfigured_account(amount=500.0)
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act / Assert
        with self.assertRaisesRegex(UserError, "no pertenece a la cuenta de anticipos"):
            self._create_register_wizard(
                invoice,
                amount=100.0,
                l10n_ve_apply_advance=True,
                l10n_ve_advance_line_id=wrong_account_line.id,
            )

    def test_apply_advance_rejects_non_positive_amount(self):
        # Arrange
        advance_line = self._create_open_advance_line(amount=500.0)
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act / Assert
        with self.assertRaisesRegex(UserError, "debe ser mayor que cero"):
            self._create_register_wizard(
                invoice,
                amount=0.0,
                l10n_ve_apply_advance=True,
                l10n_ve_advance_line_id=advance_line.id,
            )

    def test_apply_advance_rejects_amount_over_available_advance(self):
        # Arrange
        advance_line = self._create_open_advance_line(amount=200.0)
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act / Assert
        with self.assertRaisesRegex(UserError, "más del anticipo disponible"):
            self._create_register_wizard(
                invoice,
                amount=300.0,
                l10n_ve_apply_advance=True,
                l10n_ve_advance_line_id=advance_line.id,
            )

    def test_apply_advance_rejects_amount_over_invoice_residual(self):
        # Arrange
        advance_line = self._create_open_advance_line(amount=2000.0)
        invoice = self._create_customer_invoice(amount=1000.0)

        # Act / Assert
        with self.assertRaisesRegex(
            UserError, "más del importe pendiente de la factura"
        ):
            self._create_register_wizard(
                invoice,
                amount=1500.0,
                l10n_ve_apply_advance=True,
                l10n_ve_advance_line_id=advance_line.id,
            )
