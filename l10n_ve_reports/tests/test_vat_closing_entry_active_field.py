from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestVatClosingEntryActiveAccountField(TestAccountReportsCommon):
    """`_compute_vat_closing_entry`'s empty-period fallback
    (models/account_generic_tax_report.py:487,499) filters
    `account.tax.repartition.line` by `account_id.deprecated`, a field
    removed from `account.account` in Odoo 18+ and replaced by `active`
    (odoo19-core/addons/account/models/account_account.py has no
    `deprecated` field declaration). Any closing period with zero tax
    move lines (e.g. a fresh company with no posted invoices yet) hits
    this crash, independently of the bucket-12 tax group misconfiguration
    guard.
    """

    def test_empty_period_closing_entry_does_not_reference_deprecated_field(self):
        company = self.company_data["company"]
        report = self.env.ref("account.generic_tax_report")
        options = self._generate_options(report, "2024-01-01", "2024-01-31")

        # Must not raise ValueError: Invalid field account.account.deprecated.
        line_ids_vals, tax_group_subtotal = self.env[
            "account.tax.report.handler.oca"
        ]._compute_vat_closing_entry(company, options)

        self.assertIsInstance(line_ids_vals, list)
        self.assertIsInstance(tax_group_subtotal, dict)
