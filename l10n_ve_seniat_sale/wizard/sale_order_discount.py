# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class SaleOrderDiscount(models.TransientModel):
    _inherit = "sale.order.discount"

    l10n_ve_discount_reason_id = fields.Many2one(
        comodel_name="l10n.ve.discount.reason",
        string="Razón de descuento",
        required=True,
    )
    l10n_ve_discount_mode = fields.Selection(
        selection=[
            ("percentage", "Porcentaje"),
            ("amount", "Monto fijo"),
        ],
        string="Tipo de descuento",
        default="percentage",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "l10n_ve_discount_reason_id" in fields_list and not res.get(
            "l10n_ve_discount_reason_id"
        ):
            default_reason = self.env["l10n.ve.discount.reason"]._l10n_ve_get_default()
            if default_reason:
                res["l10n_ve_discount_reason_id"] = default_reason.id
        return res

    def _l10n_ve_compute_global_discount_amount(self):
        self.ensure_one()
        order = self.sale_order_id
        if self.l10n_ve_discount_mode == "amount":
            if not order.amount_total:
                return 0.0
            return self.discount_amount

        discount_percentage = self.discount_percentage
        total_discount = 0.0
        for line in order.order_line:
            if not line.product_uom_qty or not line.price_unit:
                continue
            if line.display_type or line.is_downpayment:
                continue
            disc_product = order.company_id.sale_discount_product_id
            if disc_product and line.product_id == disc_product:
                continue
            taxes = line.tax_id.flatten_taxes_hierarchy()
            taxes -= taxes.filtered(lambda tax: tax.amount_type == "fixed")
            line_base = line.price_unit * (1 - (line.discount or 0.0) / 100) * line.product_uom_qty
            total_discount += line_base * discount_percentage
        return total_discount

    def _l10n_ve_apply_ve_global_discount(self):
        self.ensure_one()
        self = self.with_company(self.company_id)
        order = self.sale_order_id
        amount = self._l10n_ve_compute_global_discount_amount()
        if float_compare(
            amount, 0.0, precision_digits=order.currency_id.decimal_places
        ) <= 0:
            return
        self.env["l10n.ve.sale.order.discount"].create(
            {
                "sale_order_id": order.id,
                "reason_id": self.l10n_ve_discount_reason_id.id,
                "amount": amount,
                "discount_type": "percentage"
                if self.l10n_ve_discount_mode == "percentage"
                else "fixed",
                "discount_percentage": self.discount_percentage
                if self.l10n_ve_discount_mode == "percentage"
                else 0.0,
            }
        )

    def action_apply_discount(self):
        self.ensure_one()
        if self.company_id.account_fiscal_country_id.code == "VE":
            order = self.sale_order_id
            if not self.l10n_ve_discount_reason_id:
                raise ValidationError(_("Seleccione la razón del descuento."))
            if self.l10n_ve_discount_mode == "percentage":
                if float_compare(self.discount_percentage, 0.0, precision_digits=10) <= 0:
                    raise ValidationError(_("Indique el porcentaje del descuento."))
                if float_compare(self.discount_percentage, 1.0, precision_digits=10) >= 0:
                    raise ValidationError(
                        _("No se permite un descuento global del 100%% en el pedido.")
                    )
                if order.l10n_ve_global_discount_ids.filtered(
                    lambda discount: discount.discount_type == "percentage"
                ):
                    raise ValidationError(_("Solo puede existir un descuento global por porcentaje."))
            else:
                if not order or not order.amount_total:
                    raise ValidationError(_("Indique el monto del descuento."))
                so_amount = order.amount_total
                if any(
                    tax.amount_type == "fixed"
                    for tax in order.order_line.tax_id.flatten_taxes_hierarchy()
                ):
                    fixed_taxes_amount = 0
                    for line in order.order_line:
                        taxes = line.tax_id.flatten_taxes_hierarchy()
                        for tax in taxes.filtered(lambda t: t.amount_type == "fixed"):
                            fixed_taxes_amount += tax.amount * line.product_uom_qty
                    so_amount -= fixed_taxes_amount
                if so_amount and float_compare(
                    self.discount_amount,
                    so_amount,
                    precision_digits=self.currency_id.decimal_places,
                ) >= 0:
                    raise ValidationError(
                        _("No se permite un descuento del 100%% del importe del pedido.")
                    )
                if float_compare(
                    self.discount_amount,
                    0.0,
                    precision_digits=self.currency_id.decimal_places,
                ) <= 0:
                    raise ValidationError(_("Indique el monto del descuento."))
            self._l10n_ve_apply_ve_global_discount()
            return
        return super().action_apply_discount()

    def _prepare_discount_product_values(self):
        vals = super()._prepare_discount_product_values()
        company = self.company_id
        if company.account_fiscal_country_id.code != "VE":
            return vals
        sale_tax = company.account_sale_tax_id
        purchase_tax = company.account_purchase_tax_id
        if sale_tax:
            vals["taxes_id"] = [(6, 0, [sale_tax.id])]
        if purchase_tax:
            vals["supplier_taxes_id"] = [(6, 0, [purchase_tax.id])]
        return vals
