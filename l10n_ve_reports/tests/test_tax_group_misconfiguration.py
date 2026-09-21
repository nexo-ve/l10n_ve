from unittest.mock import patch

from odoo.exceptions import RedirectWarning
from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestTaxGroupMisconfiguration(TestAccountReportsCommon):
    """Cover the ported ``_check_misconfigured_tax_groups`` predicate
    (bucket 12, models/account_tax.py) and the pre-existing
    ``_redirect_to_misconfigured_tax_groups`` action it feeds
    (models/account_generic_tax_report.py:686-708).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.countries = cls.company.account_fiscal_country_id

    def test_missing_payable_account_raises_redirect(self):
        """A tax group missing ``tax_payable_account_id`` must be reported
        as misconfigured by the predicate (mirrors the skip rule at
        models/account_generic_tax_report.py:446) and must trigger the
        existing RedirectWarning action, not an AttributeError.
        """
        self.env["account.tax.group"].create(
            {
                "name": "Misconfigured Tax Group",
                "company_id": self.company.id,
                "country_id": self.countries.id,
                "tax_receivable_account_id": self.company_data[
                    "default_account_receivable"
                ].id,
                # tax_payable_account_id intentionally left unset.
            }
        )

        misconfigured = self.env[
            "account.tax.group"
        ]._check_misconfigured_tax_groups(self.company, self.countries)
        self.assertTrue(
            misconfigured,
            "a tax group missing tax_payable_account_id must be reported "
            "as misconfigured",
        )

        with self.assertRaises(RedirectWarning) as capture:
            self.env[
                "account.tax.report.handler.oca"
            ]._redirect_to_misconfigured_tax_groups(self.company, self.countries)

        action = capture.exception.args[1]
        self.assertEqual(action["res_model"], "account.tax.group")
        self.assertIn(("country_id", "=", False), action["domain"])
        self.assertIn(
            ("country_id", "in", self.countries.ids), action["domain"]
        )

    def test_group_without_country_missing_account_is_flagged(self):
        """A tax group with no ``country_id`` (shared across countries) and
        missing a required account must still be reported as misconfigured.
        The redirect action's domain already includes country-less groups
        (``("country_id", "=", False)``) and the closing entry query does
        not filter tax groups by country at all, so the predicate must not
        silently skip them either.
        """
        tax_groups = self.env["account.tax.group"].search(
            self.env["account.tax.group"]._check_company_domain(self.company)
        )
        tax_groups.write(
            {
                "tax_payable_account_id": self.company_data[
                    "default_account_payable"
                ].id,
                "tax_receivable_account_id": self.company_data[
                    "default_account_receivable"
                ].id,
            }
        )
        self.env["account.tax.group"].create(
            {
                "name": "Country-less Misconfigured Tax Group",
                "company_id": self.company.id,
                "country_id": False,
                "tax_receivable_account_id": self.company_data[
                    "default_account_receivable"
                ].id,
                # tax_payable_account_id intentionally left unset.
            }
        )

        misconfigured = self.env[
            "account.tax.group"
        ]._check_misconfigured_tax_groups(self.company, self.countries)
        self.assertTrue(
            misconfigured,
            "a country-less tax group missing tax_payable_account_id must "
            "still be reported as misconfigured",
        )

    def test_fully_configured_group_posts_closing(self):
        """When every tax group of the company has both required accounts
        set, the predicate must be falsy and the closing entry must be
        generated without a RedirectWarning.
        """
        tax_groups = self.env["account.tax.group"].search(
            self.env["account.tax.group"]._check_company_domain(self.company)
        )
        self.assertTrue(
            tax_groups, "the fixture company must expose at least one tax group"
        )
        tax_groups.write(
            {
                "tax_payable_account_id": self.company_data[
                    "default_account_payable"
                ].id,
                "tax_receivable_account_id": self.company_data[
                    "default_account_receivable"
                ].id,
            }
        )

        misconfigured = self.env[
            "account.tax.group"
        ]._check_misconfigured_tax_groups(self.company, self.countries)
        self.assertFalse(
            misconfigured,
            "every tax group has both required accounts set; the "
            "predicate must not flag any",
        )

        report = self.env.ref("account.generic_tax_report")
        options = self._generate_options(report, "2024-01-01", "2024-01-31")

        with patch.object(
            type(self.env["account.move"]),
            "_get_vat_report_attachments",
            autospec=True,
            side_effect=lambda *args, **kwargs: [],
        ):
            closing_moves = self.env[
                "account.tax.report.handler.oca"
            ]._generate_tax_closing_entries(report, options, companies=self.company)

        self.assertTrue(
            closing_moves,
            "the closing move must be created without a RedirectWarning",
        )
