from odoo import Command, fields

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class L10nVePaymentAdvanceCommon(AccountTestInvoicingCommon):
    """Shared fixtures for l10n_ve_payment_advance tests.

    This module only depends on ``account``, so we build on top of
    ``AccountTestInvoicingCommon`` directly (no l10n_ve_seniat dependency).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env.company
        cls.currency = cls.company.currency_id
        cls.bank_journal = cls.company_data["default_journal_bank"]

        cls.customer_advance_account = cls.env["account.account"].create(
            {
                "name": "Customer Advances Test",
                "code": "210901",
                "account_type": "liability_current",
                "reconcile": True,
                "company_ids": [Command.set([cls.company.id])],
            }
        )
        cls.supplier_advance_account = cls.env["account.account"].create(
            {
                "name": "Supplier Advances Test",
                "code": "110901",
                "account_type": "asset_current",
                "reconcile": True,
                "company_ids": [Command.set([cls.company.id])],
            }
        )
        cls.company.write(
            {
                "account_customer_advance_id": cls.customer_advance_account.id,
                "account_supplier_advance_id": cls.supplier_advance_account.id,
            }
        )

        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Advance Test Customer",
                "invoice_sending_method": "manual",
                "invoice_edi_format": False,
                "property_account_receivable_id": cls.company_data[
                    "default_account_receivable"
                ].id,
                "property_account_payable_id": cls.company_data[
                    "default_account_payable"
                ].id,
                "company_id": False,
            }
        )
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Advance Test Supplier",
                "invoice_sending_method": "manual",
                "invoice_edi_format": False,
                "property_account_receivable_id": cls.company_data[
                    "default_account_receivable"
                ].id,
                "property_account_payable_id": cls.company_data[
                    "default_account_payable"
                ].id,
                "company_id": False,
            }
        )

    @classmethod
    def _create_customer_invoice(cls, partner=None, amount=1000.0, post=True):
        invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": (partner or cls.customer).id,
                "invoice_date": fields.Date.context_today(cls.env["account.move"]),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Test line",
                            "quantity": 1.0,
                            "price_unit": amount,
                            "account_id": cls.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        if post:
            invoice.action_post()
        return invoice

    @classmethod
    def _create_vendor_bill(cls, partner=None, amount=1000.0, post=True):
        bill = cls.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": (partner or cls.supplier).id,
                "invoice_date": fields.Date.context_today(cls.env["account.move"]),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Test line",
                            "quantity": 1.0,
                            "price_unit": amount,
                            "account_id": cls.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        if post:
            bill.action_post()
        return bill

    @classmethod
    def _create_standalone_payment(
        cls, partner, partner_type, payment_type, amount=500.0, post=True
    ):
        payment = cls.env["account.payment"].create(
            {
                "partner_id": partner.id,
                "partner_type": partner_type,
                "payment_type": payment_type,
                "amount": amount,
                "journal_id": cls.bank_journal.id,
                "date": fields.Date.context_today(cls.env["account.payment"]),
            }
        )
        if post:
            payment.action_post()
        return payment

    @classmethod
    def _create_register_wizard(cls, invoices, **vals):
        return (
            cls.env["account.payment.register"]
            .with_context(
                active_model="account.move",
                active_ids=invoices.ids,
                active_id=invoices[:1].id,
            )
            .create(
                {
                    "journal_id": cls.bank_journal.id,
                    **vals,
                }
            )
        )
