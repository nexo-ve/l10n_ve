# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.modules.module import get_manifest
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_path


@tagged("post_install", "-at_install")
class TestBridgeInstall(TransactionCase):
    """Once l10n_ve_reports_seniat is installed, every fiscal-book report,
    client action and SENIAT menu it owns must resolve.
    """

    def test_fiscal_book_reports_resolve(self):
        for xml_id in (
            "l10n_ve_reports_seniat.sales_book_report",
            "l10n_ve_reports_seniat.purchases_book_report",
            "l10n_ve_reports_seniat.sales_book_fiscal_machine_report",
            "l10n_ve_reports_seniat.ve_report_x",
        ):
            with self.subTest(xml_id=xml_id):
                self.assertTrue(self.env.ref(xml_id, raise_if_not_found=False))

    def test_client_actions_resolve(self):
        for xml_id in (
            "l10n_ve_reports_seniat.action_account_report_ve_report_x",
            "l10n_ve_reports_seniat.action_account_report_sales_book",
            "l10n_ve_reports_seniat.action_account_report_sales_book_fiscal_machine",
            "l10n_ve_reports_seniat.action_account_report_purchases_book",
        ):
            with self.subTest(xml_id=xml_id):
                self.assertTrue(self.env.ref(xml_id, raise_if_not_found=False))

    def test_seniat_menus_resolve(self):
        for xml_id in (
            "l10n_ve_reports_seniat.menu_seniat_report_general_ledger",
            "l10n_ve_reports_seniat.menu_seniat_report_bank_book",
            "l10n_ve_reports_seniat.menu_seniat_report_cash_book",
            "l10n_ve_reports_seniat.menu_seniat_report_diary_book",
            "l10n_ve_reports_seniat.menu_seniat_report_daily_payments",
            "l10n_ve_reports_seniat.menu_seniat_report_ve_report_x",
            "l10n_ve_reports_seniat.menu_seniat_report_sales_book",
            "l10n_ve_reports_seniat.menu_seniat_report_purchases_book",
            "l10n_ve_reports_seniat.menu_seniat_report_sales_book_fiscal_machine",
        ):
            with self.subTest(xml_id=xml_id):
                self.assertTrue(self.env.ref(xml_id, raise_if_not_found=False))

    def test_audit_reports_menus_resolve_under_bridge(self):
        """The four fiscal-book menus under Audit Reports moved from
        l10n_ve_reports to l10n_ve_reports_seniat (S1-T13); they must
        resolve under the bridge's own module prefix and point at the
        bridge's own client actions, not at leftover generic records.
        """
        pairs = (
            (
                "l10n_ve_reports_seniat.menu_action_account_report_ve_report_x",
                "l10n_ve_reports_seniat.action_account_report_ve_report_x",
            ),
            (
                "l10n_ve_reports_seniat.menu_action_account_report_sales_book",
                "l10n_ve_reports_seniat.action_account_report_sales_book",
            ),
            (
                "l10n_ve_reports_seniat.menu_action_account_report_sales_book_fiscal_machine",
                "l10n_ve_reports_seniat.action_account_report_sales_book_fiscal_machine",
            ),
            (
                "l10n_ve_reports_seniat.menu_action_account_report_purchases_book",
                "l10n_ve_reports_seniat.action_account_report_purchases_book",
            ),
        )
        for menu_xml_id, action_xml_id in pairs:
            with self.subTest(menu_xml_id=menu_xml_id, action_xml_id=action_xml_id):
                menu = self.env.ref(menu_xml_id, raise_if_not_found=False)
                action = self.env.ref(action_xml_id, raise_if_not_found=False)
                self.assertTrue(menu)
                self.assertTrue(action)
                self.assertEqual(menu.action, action)

    def test_pdf_export_scss_asset_ships_with_bridge(self):
        """The sales-book PDF export stylesheet moved with the models and
        data it styles; it must still exist under the bridge module and
        be declared in the bridge's own asset bundle contribution.
        """
        self.assertTrue(
            file_path("l10n_ve_reports_seniat/static/src/scss/sales_book_report.scss")
        )
        manifest = get_manifest("l10n_ve_reports_seniat")
        assets = manifest.get("assets", {})
        self.assertIn("l10n_ve_reports.assets_pdf_export", assets)
        self.assertIn(
            "l10n_ve_reports_seniat/static/src/scss/sales_book_report.scss",
            assets["l10n_ve_reports.assets_pdf_export"],
        )

    def test_audit_reports_menu_order_matches_pre_split_layout(self):
        """The Audit Reports menu tree must keep the exact same visible
        order it had before the fiscal-book menus moved to this bridge
        module (pre-split order was purely by XML declaration / creation
        id, since none of the 11 children set an explicit sequence).
        """
        audit_reports_menu = self.env.ref(
            "l10n_ve_reports.account_reports_audit_reports_menu"
        )
        expected_names = [
            "🇻🇪 General Ledger",
            "🇻🇪 Libro Diario",
            "🇻🇪 Libro de Banco",
            "🇻🇪 Libro de Caja",
            "🇻🇪 Pagos por diario",
            "🇻🇪 Reporte X",
            "🇻🇪 Libro de Ventas",
            "🇻🇪 Libro de Ventas Maquina Fiscal",
            "🇻🇪 Libro de Compras",
            "🇻🇪 Trial Balance",
            "🇻🇪 Journal Audit",
        ]
        self.assertEqual(audit_reports_menu.child_id.mapped("name"), expected_names)
