# Part of Odoo. See LICENSE file for full copyright and licensing details.

import unittest

from odoo import Command, fields

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon

# Credit-currency units per 1 unit of company currency, e.g. 1 credit-currency
# unit = 50 company-currency units. res.currency.rate.rate follows this
# "foreign units per 1 base unit" convention (see base
# ResCurrency._get_rates/_compute_current_rate), which is also what
# res.currency._get_conversion_rate(company_currency, credit_currency, ...)
# returns directly.
CREDIT_RATE = 0.02

# Company-currency net (tax-excluded) price for a line that must convert to
# exactly 10.00 credit-currency units at CREDIT_RATE.
PRODUCT_PRICE = 500.0


class L10nVePosCreditCurrencyCommon(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "pos.order" not in cls.env:
            # `raise unittest.SkipTest` in `setUpClass` is the documented
            # way to skip every test in the class: it reports them as
            # SKIPPED. A bare `return` instead leaves the class half-built,
            # so tests die with an unrelated `AttributeError` on the first
            # missing fixture attribute instead of being reported as
            # skipped (defect F11).
            raise unittest.SkipTest("point_of_sale is not installed")

        cls.env.user.group_ids += cls.env.ref("point_of_sale.group_pos_manager")

        cls.today = fields.Date.today()
        cls.company_currency = cls.env.company.currency_id
        # `L10nVeSeniatCommon` only sets the company's fiscal country to VE;
        # it does not force the company currency to VES (verified: neither
        # the "ve_seniat" chart template data nor `change_company_country`
        # touch `currency_id`). Pick USD as the credit currency, unless the
        # company currency already IS USD (as in `l10n_ve_loyalty_pos`'s
        # ewallet tests), in which case fall back to EUR so the tests stay
        # deterministic regardless of which currency the test company ends
        # up with.
        usd = cls.env.ref("base.USD")
        eur = cls.env.ref("base.EUR")
        cls.credit_currency = eur if cls.company_currency == usd else usd
        cls.credit_currency.sudo().active = True

        cls._create_rate(cls.today, CREDIT_RATE)

        # A Venezuelan POS sale always carries IVA: `L10nVeSeniatCommon`
        # normalizes the company's default sale tax to 16%
        # (`_l10n_ve_normalize_default_taxes`), and `l10n_ve_seniat`'s
        # `account.move.line.create()`/`write()` override
        # (`_put_unique_tax_per_line`) force-applies that same tax to any VE
        # `out_invoice`/`out_refund` line left with zero `tax_ids` regardless
        # of the product's own configuration. Giving the product this tax
        # explicitly, and propagating it onto every POS order line created in
        # these tests (see `_create_pos_order` below), means the invoice
        # lines carry the REAL company tax from the start instead of relying
        # on that force-add fallback, so every expected amount below is
        # derived from the tax rate rather than hardcoded.
        cls.sale_tax = cls.company_data["default_tax_sale"]

        cls.partner_credit = cls.env["res.partner"].create(
            {
                "name": "POS Credit Currency Partner",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J12399887",
            }
        )
        cls.product_credit = cls.env["product.product"].create(
            {
                "name": "POS Credit Currency Product",
                "type": "service",
                "available_in_pos": True,
                "list_price": PRODUCT_PRICE,
                "taxes_id": [Command.set(cls.sale_tax.ids)],
                "property_account_income_id": cls.company_data[
                    "default_account_revenue"
                ].id,
            }
        )
        # `_create_payment_moves` (core `pos.payment`) posts the counterpart
        # of every non-`pay_later` payment to
        # `company.account_default_pos_receivable_account_id` (the POS
        # suspense/receivable account) until session close nets it against
        # cash/bank. `AccountTestInvoicingCommon` does not set this field, so
        # without it that counterpart line has no account and the insert
        # fails the `account_move_line_check_accountable_required_fields`
        # check constraint. Core's own POS test common
        # (`point_of_sale/tests/common.py`) sets a dedicated account for the
        # same reason; mirror that here.
        cls.pos_receivable_account = cls.env["account.account"].create(
            {
                "code": "X1099POS",
                "name": "POS Receivable (credit currency tests)",
                "account_type": "asset_receivable",
                "reconcile": True,
            }
        )
        cls.env.company.account_default_pos_receivable_account_id = (
            cls.pos_receivable_account.id
        )

        cls.cash_payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Cash (credit currency tests)",
                "journal_id": cls.company_data["default_journal_cash"].id,
                "receivable_account_id": cls.company_data[
                    "default_account_receivable"
                ].id,
            }
        )
        cls.pay_later_payment_method = cls.env["pos.payment.method"].create(
            {
                "name": "Customer Account (credit currency tests)",
                "receivable_account_id": cls.company_data[
                    "default_account_receivable"
                ].id,
                "split_transactions": True,
            }
        )
        cls.pos_config = cls.env["pos.config"].create(
            {
                "name": "Credit Currency Test POS",
                "company_id": cls.env.company.id,
                "journal_id": cls.company_data["default_journal_sale"].id,
                "invoice_journal_id": cls.company_data["default_journal_sale"].id,
                "payment_method_ids": [
                    Command.set(
                        (cls.cash_payment_method | cls.pay_later_payment_method).ids
                    )
                ],
            }
        )
        cls.pos_config.l10n_ve_pos_credit_invoice_currency_id = cls.credit_currency.id
        if not cls.pos_config.current_session_id:
            cls.pos_config.open_ui()
        cls.session = cls.pos_config.current_session_id

    @classmethod
    def _create_rate(cls, date, rate, currency=None):
        return cls.env["res.currency.rate"].create(
            {
                "currency_id": (currency or cls.credit_currency).id,
                "company_id": cls.env.company.id,
                "name": date,
                "rate": rate,
            }
        )

    @classmethod
    def _gross(cls, net_amount):
        """Company-currency `net_amount` marked up by the company's sale tax
        rate, e.g. the tax-included total of a line priced `net_amount`
        before tax. Derived from `cls.sale_tax.amount` so the expected
        values in these tests do not break if that rate ever changes."""
        return net_amount * (1 + cls.sale_tax.amount / 100.0)

    def _create_pos_order(
        self,
        price_unit=PRODUCT_PRICE,
        qty=1,
        date_order=None,
        partner=None,
        discount=0.0,
    ):
        subtotal = price_unit * qty * (1 - discount / 100.0)
        tax_amount = subtotal * self.sale_tax.amount / 100.0
        order_vals = {
            "company_id": self.env.company.id,
            "session_id": self.session.id,
            "partner_id": (partner or self.partner_credit).id,
            "amount_tax": tax_amount,
            "amount_total": subtotal + tax_amount,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "lines": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product_credit.id,
                        "qty": qty,
                        "price_unit": price_unit,
                        "discount": discount,
                        "price_subtotal": subtotal,
                        "price_subtotal_incl": subtotal + tax_amount,
                        # `pos.order.line.tax_ids` has no compute/default of
                        # its own: in the real POS UI it is only ever
                        # populated by the `_onchange_product_id` onchange,
                        # which never fires on a direct ORM `create()`. It
                        # must be set explicitly here to reproduce a normal
                        # POS sale.
                        "tax_ids": [Command.set(self.sale_tax.ids)],
                    },
                )
            ],
        }
        if date_order:
            order_vals["date_order"] = date_order
        return self.env["pos.order"].create(order_vals)

    def _add_payment(self, order, payment_method, amount):
        payment = self.env["pos.payment"].create(
            {
                "pos_order_id": order.id,
                "payment_method_id": payment_method.id,
                "amount": amount,
            }
        )
        order.write({"amount_paid": order.amount_paid + amount})
        return payment

    def _invoice_order(self, orders):
        orders.write({"to_invoice": True})
        return orders._generate_pos_order_invoice()
