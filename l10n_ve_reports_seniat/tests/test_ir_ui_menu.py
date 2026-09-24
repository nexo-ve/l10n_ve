# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeReportsSeniatIrUiMenu(L10nVeSeniatCommon):
    """The fiscal-machine-report menu rule is contributed by this bridge's
    `ir.ui.menu` `_inherit`, extending `l10n_ve_seniat`'s
    `_l10n_ve_emission_medium_menu_rules` via `super()`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= cls.env.ref("l10n_ve_seniat.group_seniat")
        cls.report_menu = cls.env.ref(
            "l10n_ve_reports_seniat.menu_seniat_report_sales_book_fiscal_machine"
        )
        cls.fiscal_medium = cls.env.ref("l10n_ve_seniat.emission_medium_fiscal_machine")

    def test_fiscal_machine_report_menu_hidden_without_medium(self):
        self.env.company.write({"l10n_ve_emission_medium_ids": [(5, 0, 0)]})
        blacklist = self.env["ir.ui.menu"]._l10n_ve_emission_medium_menus_blacklist()
        self.assertIn(self.report_menu.id, blacklist)

    def test_fiscal_machine_report_menu_visible_from_company_medium(self):
        self.env.company.write(
            {"l10n_ve_emission_medium_ids": [(6, 0, [self.fiscal_medium.id])]}
        )
        blacklist = self.env["ir.ui.menu"]._l10n_ve_emission_medium_menus_blacklist()
        self.assertNotIn(self.report_menu.id, blacklist)
