# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderFiscalPreview(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.company_data["default_journal_sale"]
        cls._l10n_ve_configure_journal_fiscal_machine(cls.journal)

    def _create_ve_product(self, name, price):
        tmpl = self.env["product.template"].create(
            {
                "name": name,
                "company_id": self.env.company.id,
                "list_price": price,
                "standard_price": price / 2,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
                "supplier_taxes_id": [
                    (6, 0, [self.company_data["default_tax_purchase"].id])
                ],
            }
        )
        return tmpl.product_variant_ids[0]

    def test_sale_order_preview_blocked_for_fiscal_machine(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente fiscal",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345680",
            }
        )
        product = self._create_ve_product("Producto fiscal", 10.0)
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 10.0,
                        },
                    )
                ],
            }
        )
        self.assertTrue(order.l10n_ve_hide_order_preview)
        with self.assertRaises(UserError):
            order.action_preview_sale_order()
