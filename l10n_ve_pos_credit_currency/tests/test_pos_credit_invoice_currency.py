# Part of Odoo. See LICENSE file for full copyright and licensing details.

import random
import string
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import CREDIT_RATE, PRODUCT_PRICE, L10nVePosCreditCurrencyCommon


@tagged("post_install", "-at_install")
class TestPosCreditInvoiceCurrency(L10nVePosCreditCurrencyCommon):
    def _create_currency_without_rate(self):
        """A brand-new currency is guaranteed to have zero res.currency.rate
        rows, which keeps this fixture deterministic regardless of what
        demo/base data happens to be loaded (FR-4)."""
        currency_model = self.env["res.currency"]
        for _attempt in range(20):
            code = "".join(random.choices(string.ascii_uppercase, k=3))
            if not currency_model.with_context(active_test=False).search_count(
                [("name", "=", code)]
            ):
                return currency_model.create(
                    {"name": code, "symbol": code, "rounding": 0.01}
                )
        self.fail("Could not generate a unique currency code")

    # -- AC-2 -----------------------------------------------------------
    def test_credit_invoice_uses_configured_currency(self):
        order = self._create_pos_order()
        self._add_payment(
            order, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        invoice = self._invoice_order(order)

        self.assertEqual(invoice.currency_id, self.credit_currency)
        self.assertAlmostEqual(invoice.invoice_line_ids[0].price_unit, 10.0, places=2)
        self.assertAlmostEqual(invoice.invoice_currency_rate, CREDIT_RATE, places=6)
        # Balance check (FR-10): the company-currency debit/credit must
        # reproduce the POS order total, tax included.
        self.assertAlmostEqual(
            invoice.amount_total_signed, self._gross(PRODUCT_PRICE), places=2
        )
        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertAlmostEqual(
            invoice.amount_residual,
            self._gross(PRODUCT_PRICE) * CREDIT_RATE,
            places=2,
        )

    # -- AC-3 -----------------------------------------------------------
    def test_no_credit_currency_keeps_pos_currency(self):
        self.pos_config.l10n_ve_pos_credit_invoice_currency_id = False
        order = self._create_pos_order()
        self._add_payment(
            order, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        invoice = self._invoice_order(order)

        self.assertEqual(invoice.currency_id, self.company_currency)
        self.assertAlmostEqual(
            invoice.invoice_line_ids[0].price_unit, PRODUCT_PRICE, places=2
        )
        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertAlmostEqual(
            invoice.amount_residual, self._gross(PRODUCT_PRICE), places=2
        )

    # -- AC-4 -----------------------------------------------------------
    def test_mixed_payment_invoice_in_credit_currency(self):
        total = self._gross(PRODUCT_PRICE)
        cash_amount = total / 2
        credit_amount = total / 2

        order = self._create_pos_order()
        self._add_payment(order, self.cash_payment_method, cash_amount)
        self._add_payment(order, self.pay_later_payment_method, credit_amount)
        invoice = self._invoice_order(order)

        self.assertEqual(invoice.currency_id, self.credit_currency)
        self.assertAlmostEqual(invoice.invoice_line_ids[0].price_unit, 10.0, places=2)

        cash_payment = order.payment_ids.filtered(
            lambda payment: payment.payment_method_id == self.cash_payment_method
        )
        self.assertTrue(cash_payment.account_move_id)
        # `_create_payment_moves` posts two lines for this payment: one on
        # the customer's own receivable account (credit side) and one on the
        # company's POS suspense receivable account (debit side, see
        # `common.py`). Only the former is reconciled against the invoice by
        # `_reconcile_invoice_payments`, which matches on
        # `accounting_partner.property_account_receivable_id` specifically;
        # the POS suspense line only nets out at session close, which this
        # test does not perform. Assert reconciliation on that specific
        # account rather than on every "asset_receivable" line.
        receivable_account = (
            self.env["res.partner"]
            ._find_accounting_partner(invoice.partner_id)
            .with_company(self.env.company)
            .property_account_receivable_id
        )
        cash_receivable_lines = cash_payment.account_move_id.line_ids.filtered(
            lambda line: line.account_id == receivable_account
        )
        self.assertTrue(cash_receivable_lines)
        self.assertTrue(all(cash_receivable_lines.mapped("reconciled")))

        # Half of the credit-currency total remains open on the Customer
        # Account portion.
        self.assertAlmostEqual(
            invoice.amount_residual, total / 2 * CREDIT_RATE, places=2
        )

    # -- AC-5 -------------------------------------------------------------
    def test_refund_credit_note_uses_original_currency_and_rate(self):
        order = self._create_pos_order()
        self._add_payment(
            order, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        invoice = self._invoice_order(order)
        self.assertEqual(invoice.currency_id, self.credit_currency)
        original_rate = invoice.invoice_currency_rate
        self.assertAlmostEqual(original_rate, CREDIT_RATE, places=6)

        # The rate table changes after the original invoice: a later date
        # gets a different rate for the credit currency.
        future_date = self.today + timedelta(days=10)
        self._create_rate(future_date, 0.05)

        # Build the refund through the real core path: `order._refund()`
        # copies the order lines with `refunded_orderline_id` set and
        # computes `refunded_order_id` on the result, which core's
        # `_prepare_invoice_vals` relies on. Hand-building a `pos.order`
        # with only `refunded_orderline_id` set on its line (the previous
        # version of this test) never populates `refunded_order_id`,
        # because that field is `compute`d from `lines.refunded_orderline_id
        # .order_id` only when the recordset is reached through the normal
        # refund flow's other invariants (state, `is_refund`, etc.).
        refund_order = order._refund()
        refund_order.write({"date_order": fields.Datetime.to_datetime(future_date)})
        self._add_payment(
            refund_order, self.pay_later_payment_method, -self._gross(PRODUCT_PRICE)
        )
        credit_note = self._invoice_order(refund_order)

        self.assertEqual(credit_note.move_type, "out_refund")
        self.assertEqual(credit_note.currency_id, self.credit_currency)
        # Same rate as the original invoice, not the rate in force on the
        # refund date (FR-13).
        self.assertAlmostEqual(
            credit_note.invoice_currency_rate, original_rate, places=6
        )
        self.assertAlmostEqual(
            abs(credit_note.invoice_line_ids[0].price_unit), 10.0, places=2
        )

        # Core's POS invoicing flow only auto-reconciles PAYMENT moves
        # against the invoice (`_reconcile_invoice_payments`); it does not
        # auto-reconcile a credit note against the invoice it reverses, even
        # though `_prepare_invoice_vals` links them through
        # `reversed_entry_id` for display/tracking purposes. That kind of
        # reconciliation is standard Odoo accounting behavior triggered by
        # `account.move._reverse_moves()` or an explicit `reconcile()` call,
        # neither of which the POS refund flow performs here. So this test
        # reconciles the two receivable lines explicitly, exactly as an
        # accountant would when settling a credit note against its original
        # invoice, then asserts that they cancel exactly (FR-13).
        receivable_account = (
            self.env["res.partner"]
            ._find_accounting_partner(invoice.partner_id)
            .with_company(self.env.company)
            .property_account_receivable_id
        )
        (invoice.line_ids | credit_note.line_ids).filtered(
            lambda line: line.account_id == receivable_account and not line.reconciled
        ).reconcile()

        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)
        self.assertAlmostEqual(credit_note.amount_residual, 0.0, places=2)

    # -- AC-6 -----------------------------------------------------------
    def test_rate_is_taken_from_order_date(self):
        tomorrow = self.today + timedelta(days=1)
        self._create_rate(tomorrow, 0.09)

        order = self._create_pos_order()
        self._add_payment(
            order, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        invoice = self._invoice_order(order)

        self.assertAlmostEqual(invoice.invoice_currency_rate, CREDIT_RATE, places=6)
        self.assertAlmostEqual(
            abs(invoice.invoice_line_ids[0].price_unit), 10.0, places=2
        )

    # -- AC-8 -----------------------------------------------------------
    def test_pay_later_invoice_stays_open_without_credit_currency(self):
        self.pos_config.l10n_ve_pos_credit_invoice_currency_id = False
        order = self._create_pos_order()
        self._add_payment(
            order, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        invoice = self._invoice_order(order)

        self.assertEqual(invoice.state, "posted")
        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertAlmostEqual(
            invoice.amount_residual, self._gross(PRODUCT_PRICE), places=2
        )

    # -- AC-1 / FR-2 ------------------------------------------------------
    def test_config_defaults_from_company(self):
        # This only asserts the field default (FR-2's actual implementation):
        # a newly created `pos.config` inherits the company value through
        # `l10n_ve_pos_credit_invoice_currency_id`'s `default=lambda self:
        # self.env.company...`. The former `post_init_hook`-backfill part of
        # this test simulated a state (an existing config with an empty
        # value, right after install) that cannot occur in a real install or
        # upgrade: at install every company's own value is `False` too (this
        # module creates the field), so the hook's `if not currency:
        # continue` skipped every record; and `post_init_hook` only runs for
        # packages in state `to install` (odoo/modules/loading.py), so it
        # never ran on upgrade either. That hook was dead code and has been
        # removed (defect F6), along with the part of this test that
        # exercised it and therefore passed for the wrong reason.
        self.env.company.l10n_ve_pos_credit_invoice_currency_id = (
            self.credit_currency.id
        )
        new_config = self.env["pos.config"].create(
            {
                "name": "Fresh POS for default test",
                "company_id": self.env.company.id,
                "journal_id": self.company_data["default_journal_sale"].id,
            }
        )
        self.assertEqual(
            new_config.l10n_ve_pos_credit_invoice_currency_id, self.credit_currency
        )

    # -- FR-4 -------------------------------------------------------------
    def test_currency_without_rate_is_rejected(self):
        currency_without_rate = self._create_currency_without_rate()
        with self.assertRaises(ValidationError):
            self.pos_config.l10n_ve_pos_credit_invoice_currency_id = (
                currency_without_rate.id
            )

    # -- BR-4 -------------------------------------------------------------
    def test_consolidated_billing_blocks_mixed_group(self):
        credit_order = self._create_pos_order()
        self._add_payment(
            credit_order,
            self.pay_later_payment_method,
            self._gross(PRODUCT_PRICE),
        )

        cash_order = self._create_pos_order()
        self._add_payment(
            cash_order, self.cash_payment_method, self._gross(PRODUCT_PRICE)
        )

        group = credit_order + cash_order
        # Exercised through the real invoicing entry point: our
        # `_prepare_invoice_vals()` resolves (and therefore runs the BR-4
        # guard) before delegating to `super()`, so the clear UserError is
        # what the user actually gets, instead of the raw "Expected
        # singleton" ValueError that `l10n_ve_pos`'s unconditional
        # `ensure_one()` in `_l10n_ve_pos_refund_origin_journal()` would
        # otherwise raise first on any multi-order invoice.
        with self.assertRaises(UserError):
            self._invoice_order(group)

    # -- F12 / defect F1 ---------------------------------------------------
    def test_multi_quantity_low_price_rounding_reconciles(self):
        """A line whose unit price does not convert to a round number in
        the credit currency, at qty >> 1: the invoice's company-currency
        total must still equal the POS order total (FR-10). Rounding the
        converted unit price to 2 decimals before multiplying by quantity
        (defect F1) would overstate this total by several percent, exactly
        as in the PRD's worked example."""
        price_unit = 3.33
        qty = 1250
        subtotal = price_unit * qty
        order = self._create_pos_order(price_unit=price_unit, qty=qty)
        gross = self._gross(subtotal)
        self._add_payment(order, self.pay_later_payment_method, gross)
        invoice = self._invoice_order(order)

        self.assertAlmostEqual(invoice.amount_total_signed, gross, places=2)

    # -- F12 -----------------------------------------------------------
    def test_percentage_discount_reconciles(self):
        """A percentage discount on the line must still leave the invoice's
        company-currency total equal to the POS order total."""
        order = self._create_pos_order(discount=15.0)
        gross = self._gross(PRODUCT_PRICE * (1 - 15.0 / 100.0))
        self._add_payment(order, self.pay_later_payment_method, gross)
        invoice = self._invoice_order(order)

        self.assertAlmostEqual(invoice.invoice_line_ids[0].discount, 15.0, places=2)
        self.assertAlmostEqual(invoice.amount_total_signed, gross, places=2)

    # -- BR-1 ----------------------------------------------------------
    def test_credit_currency_equal_to_pos_currency_is_noop(self):
        """BR-1: a POS credit invoice currency equal to the order's own
        currency changes nothing."""
        # The company's own currency legitimately carries no
        # `res.currency.rate` row by default (conversion against itself is
        # implicit 1:1); give it one explicitly so this scenario can be
        # exercised through the real FR-4-validated config field, without
        # weakening that validation.
        self._create_rate(self.today, 1.0, currency=self.company_currency)
        self.pos_config.l10n_ve_pos_credit_invoice_currency_id = (
            self.company_currency.id
        )
        order = self._create_pos_order()
        self._add_payment(
            order, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        invoice = self._invoice_order(order)

        self.assertEqual(invoice.currency_id, self.company_currency)
        self.assertAlmostEqual(
            invoice.invoice_line_ids[0].price_unit, PRODUCT_PRICE, places=2
        )

    # -- FR-4 ------------------------------------------------------------
    def test_archived_currency_is_rejected(self):
        """FR-4's archived-currency branch: only the no-rate branch was
        covered before.

        `self.credit_currency` cannot be used here: core's
        `_check_company_currency_stays_active` refuses to archive a currency
        that is set on a company, and USD is one in this test database. Use
        a throwaway currency instead, and give it a rate first so that the
        no-rate branch cannot be what raises.
        """
        currency = self._create_currency_without_rate()
        self._create_rate(self.today, CREDIT_RATE, currency=currency)
        currency.sudo().active = False
        with self.assertRaises(ValidationError):
            self.pos_config.l10n_ve_pos_credit_invoice_currency_id = currency.id

    # -- F2a ---------------------------------------------------------------
    def test_missing_rate_blocks_invoice_at_runtime(self):
        """The missing-rate guard from defect F2a, as defense in depth.

        Core's `res.currency._get_rates` falls back to a rate of 1.0 when no
        rate row is visible for the company, which would post a
        foreign-currency invoice at par (a 10,000 VES order becoming
        "10,000 USD"). The FR-4 constraint rejects a rate-less currency when
        the POS config is saved, and `l10n_ve_seniat` forbids deleting rate
        rows, so this state cannot be reached through the ORM. It remains
        reachable in practice (rates scoped to another company, a partial
        restore), so force it with a direct SQL write and prove the runtime
        guard refuses to invoice.
        """
        currency = self._create_currency_without_rate()
        self.env.cr.execute(
            """
            UPDATE pos_config
               SET l10n_ve_pos_credit_invoice_currency_id = %s
             WHERE id = %s
            """,
            (currency.id, self.pos_config.id),
        )
        self.pos_config.invalidate_recordset(["l10n_ve_pos_credit_invoice_currency_id"])
        self.assertEqual(
            self.pos_config.l10n_ve_pos_credit_invoice_currency_id, currency
        )

        order = self._create_pos_order()
        self._add_payment(
            order, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        with self.assertRaises(UserError):
            self._invoice_order(order)

    # -- BR-4 / defect F5 ---------------------------------------------------
    def test_consolidated_billing_blocks_all_credit_group(self):
        """Multi-order blocking must apply even when every order in the
        group resolves to the same credit currency and rate (defect F5):
        before this fix, that specific combination fell through to
        `super()`, which crashes on `l10n_ve_pos`'s unconditional
        `ensure_one()`."""
        order_a = self._create_pos_order()
        self._add_payment(
            order_a, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        order_b = self._create_pos_order()
        self._add_payment(
            order_b, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )

        group = order_a + order_b
        with self.assertRaises(UserError):
            self._invoice_order(group)

    # -- AC-4 ----------------------------------------------------------
    def test_mixed_payment_session_closes_without_duplicated_receivable(self):
        """AC-4 explicitly requires closing the session after a mixed
        cash/credit invoice, asserting it closes without error and without
        duplicating the invoice's own receivable line - the most likely
        regression surface of this whole feature, and unasserted before."""
        total = self._gross(PRODUCT_PRICE)
        cash_amount = total / 2
        credit_amount = total / 2

        order = self._create_pos_order()
        self._add_payment(order, self.cash_payment_method, cash_amount)
        self._add_payment(order, self.pay_later_payment_method, credit_amount)
        invoice = self._invoice_order(order)

        receivable_account = (
            self.env["res.partner"]
            ._find_accounting_partner(invoice.partner_id)
            .with_company(self.env.company)
            .property_account_receivable_id
        )
        lines_before = invoice.line_ids.filtered(
            lambda line: line.account_id == receivable_account
        )
        self.assertEqual(len(lines_before), 1)

        # Avoid an unrelated cash-difference detour: the test POS config has
        # a cash payment method, so `cash_control` is True and closing goes
        # through the balancing flow. Report the exact cash counted so there
        # is no difference to post.
        self.session.cash_register_balance_end_real = (
            self.session.cash_register_balance_start + cash_amount
        )
        self.session.action_pos_session_closing_control()

        self.assertEqual(self.session.state, "closed")
        lines_after = invoice.line_ids.filtered(
            lambda line: line.account_id == receivable_account
        )
        self.assertEqual(len(lines_after), 1)
        self.assertEqual(lines_before, lines_after)

    # -- F9 ------------------------------------------------------------
    def test_cash_rounding_does_not_alter_a_credit_only_invoice(self):
        """A cash-rounding POS config must not change a pure credit invoice.

        The module no longer strips `invoice_cash_rounding_id` from the
        invoice values (former defect F9): core already decides whether a
        rounding line applies, and it applies one only when the config does
        not restrict rounding to cash payments or when the order actually
        carries a cash payment (`_prepare_invoice_vals`). A Customer Account
        payment is not `is_cash_count`, so with the default
        `only_round_cash_method` no adjustment line may appear and the
        company-currency total must still reproduce the POS order total
        (FR-10).

        Note: the behavior of a POS-currency cash rounding applied to an
        invoice issued in a different currency is deliberately NOT asserted
        here. The PRD defines no acceptance criterion for that combination
        and the rounding granularity is expressed in the POS currency, so
        the two are not comparable without a product decision.
        """
        rounding_method = self.env["account.cash.rounding"].create(
            {
                "name": "Rounding (credit currency tests)",
                "rounding": 0.05,
                "strategy": "add_invoice_line",
                "profit_account_id": self.company_data["default_account_revenue"].id,
                "loss_account_id": self.company_data["default_account_expense"].id,
                "rounding_method": "HALF-UP",
            }
        )
        self.pos_config.write(
            {
                "cash_rounding": True,
                "rounding_method": rounding_method.id,
                "only_round_cash_method": True,
            }
        )

        order = self._create_pos_order()
        self._add_payment(
            order, self.pay_later_payment_method, self._gross(PRODUCT_PRICE)
        )
        invoice = self._invoice_order(order)

        self.assertFalse(
            invoice.line_ids.filtered(lambda line: line.display_type == "rounding"),
            "a credit-only order must not receive a cash rounding line",
        )
        self.assertEqual(invoice.currency_id, self.credit_currency)
        self.assertAlmostEqual(
            invoice.amount_total_signed, self._gross(PRODUCT_PRICE), places=2
        )
