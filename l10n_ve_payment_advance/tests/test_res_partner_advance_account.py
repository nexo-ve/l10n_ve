from odoo import Command
from odoo.tests import tagged

from .common import L10nVePaymentAdvanceCommon


@tagged("post_install", "-at_install")
class TestResPartnerAdvanceAccount(L10nVePaymentAdvanceCommon):
    def test_customer_advance_account_partner_override_wins(self):
        # Arrange
        partner_account = self.env["account.account"].create(
            {
                "name": "Partner Customer Advances",
                "code": "210902",
                "account_type": "liability_current",
                "reconcile": True,
                "company_ids": [Command.set([self.company.id])],
            }
        )
        self.customer.with_company(
            self.company
        ).property_account_customer_advance_id = partner_account

        # Act
        result = self.env["res.partner"]._get_customer_advance_account(
            self.customer, self.company
        )

        # Assert
        self.assertEqual(result, partner_account)

    def test_customer_advance_account_falls_back_to_company(self):
        # Arrange: customer has no partner-level advance account configured

        # Act
        result = self.env["res.partner"]._get_customer_advance_account(
            self.customer, self.company
        )

        # Assert
        self.assertEqual(result, self.customer_advance_account)

    def test_customer_advance_account_returns_empty_without_company(self):
        # Act
        result = self.env["res.partner"]._get_customer_advance_account(
            self.customer, self.env["res.company"]
        )

        # Assert
        self.assertFalse(result)
        self.assertEqual(result._name, "account.account")

    def test_supplier_advance_account_partner_override_wins(self):
        # Arrange
        partner_account = self.env["account.account"].create(
            {
                "name": "Partner Supplier Advances",
                "code": "110902",
                "account_type": "asset_current",
                "reconcile": True,
                "company_ids": [Command.set([self.company.id])],
            }
        )
        self.supplier.with_company(
            self.company
        ).property_account_supplier_advance_id = partner_account

        # Act
        result = self.env["res.partner"]._get_supplier_advance_account(
            self.supplier, self.company
        )

        # Assert
        self.assertEqual(result, partner_account)

    def test_supplier_advance_account_falls_back_to_company(self):
        # Act
        result = self.env["res.partner"]._get_supplier_advance_account(
            self.supplier, self.company
        )

        # Assert
        self.assertEqual(result, self.supplier_advance_account)

    def test_supplier_advance_account_returns_empty_without_company(self):
        # Act
        result = self.env["res.partner"]._get_supplier_advance_account(
            self.supplier, self.env["res.company"]
        )

        # Assert
        self.assertFalse(result)

    def test_get_partner_advance_account_routes_on_partner_type_supplier(self):
        # Act
        result = self.env["res.partner"]._get_partner_advance_account(
            self.supplier, self.company, "supplier"
        )

        # Assert
        self.assertEqual(result, self.supplier_advance_account)

    def test_get_partner_advance_account_routes_on_partner_type_customer(self):
        # Act: any partner_type other than "supplier" routes to the customer account
        result = self.env["res.partner"]._get_partner_advance_account(
            self.customer, self.company, "customer"
        )

        # Assert
        self.assertEqual(result, self.customer_advance_account)
