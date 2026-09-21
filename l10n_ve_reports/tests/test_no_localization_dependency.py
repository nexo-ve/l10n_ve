# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNoLocalizationDependency(TransactionCase):
    """l10n_ve_reports must install standalone with only account/web.

    These assertions hold regardless of which database they run in: they
    check the *declared* module dependencies and the *absence* of the
    bridge's reports, not any generic-vs-VE business behaviour.
    """

    def test_no_seniat_or_withholding_dependency(self):
        module = self.env["ir.module.module"].search(
            [("name", "=", "l10n_ve_reports")]
        )
        dependency_names = module.dependencies_id.mapped("name")
        self.assertNotIn("l10n_ve_seniat", dependency_names)
        self.assertNotIn("l10n_ve_withholding", dependency_names)

    def test_sales_book_report_absent_without_bridge(self):
        bridge_installed = (
            self.env["ir.module.module"]
            .search([("name", "=", "l10n_ve_reports_seniat")])
            .state
            == "installed"
        )
        if bridge_installed:
            self.skipTest(
                "l10n_ve_reports_seniat is installed in this database; "
                "this assertion only applies to a generic-only install."
            )
        sales_book_report = self.env.ref(
            "l10n_ve_reports.sales_book_report", raise_if_not_found=False
        )
        self.assertFalse(sales_book_report)
