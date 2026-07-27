# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("ve_seniat")
    def _get_ve_seniat_template_data(self):
        return {
            "sequence": 10,
            "code_digits": "7",
            "property_account_receivable_id": "account_account_1106001",
            "property_account_payable_id": "account_account_2101002",
            "property_account_expense_categ_id": "account_account_5101001",
            "property_account_income_categ_id": "account_account_4101001",
            "name": _("SENIAT"),
        }

    @template("ve_seniat", "res.company")
    def _get_ve_seniat_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.ve",
                "cash_account_code_prefix": "1101",
                "bank_account_code_prefix": "1102",
                "income_currency_exchange_account_id": "account_account_4102004",  # noqa: E501
                "expense_currency_exchange_account_id": "account_account_5102014",  # noqa: E501
                "tax_calculation_rounding_method": "round_globally",
                "account_sale_tax_id": "tax1sale",
                "account_purchase_tax_id": "tax1purchase",
            },
        }

    @template("ve_seniat_basic")
    def _get_ve_seniat_basic_template_data(self):
        return {
            "name": _("SENIAT - Basic"),
            "sequence": 20,
            "code_digits": "7",
            "property_account_receivable_id": "account_account_1106001",
            "property_account_payable_id": "account_account_2101002",
            "property_account_expense_categ_id": "account_account_5101001",
            "property_account_income_categ_id": "account_account_4101001",
        }

    @template("ve_seniat_basic", "res.company")
    def _get_ve_seniat_basic_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.ve",
                "cash_account_code_prefix": "1101",
                "bank_account_code_prefix": "1102",
                "income_currency_exchange_account_id": "account_account_4102004",  # noqa: E501
                "expense_currency_exchange_account_id": "account_account_5102014",  # noqa: E501
                "tax_calculation_rounding_method": "round_globally",
                "account_sale_tax_id": "tax1sale",
                "account_purchase_tax_id": "tax1purchase",
            },
        }

    @template("ve_seniat_empty")
    def _get_ve_seniat_empty_template_data(self):
        return {
            "name": _("SENIAT - Empty"),
            "sequence": 30,
        }

    @template("ve_seniat_empty", "res.company")
    def _get_ve_seniat_empty_res_company(self):
        return {
            self.env.company.id: {
                "account_fiscal_country_id": "base.ve",
                "tax_calculation_rounding_method": "round_globally",
                "account_sale_tax_id": "tax1sale",
                "account_purchase_tax_id": "tax1purchase",
            },
        }
