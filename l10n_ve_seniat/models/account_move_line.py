import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, frozendict

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    display_type = fields.Selection(
        selection_add=[("global_discount", "Global Discount")],
        ondelete={"global_discount": "cascade"},
    )

    l10n_ve_global_discount_line = fields.Boolean(
        string="Venezuela global discount line",
        readonly=True,
        copy=False,
    )
    l10n_ve_line_discount_line = fields.Boolean(
        string="Venezuela line discount line",
        readonly=True,
        copy=False,
    )
    l10n_ve_global_discount_tax_ids = fields.Many2many(
        comodel_name="account.tax",
        relation="account_move_line_l10n_ve_global_discount_tax_rel",
        column1="line_id",
        column2="tax_id",
        string="Global discount tax group",
        readonly=True,
        copy=False,
    )
    l10n_ve_global_discount_allocation_key = fields.Binary(
        compute="_compute_l10n_ve_global_discount_allocation_key",
        exportable=False,
    )
    l10n_ve_line_discount_allocation_key = fields.Binary(
        compute="_compute_l10n_ve_line_discount_allocation_key",
        exportable=False,
    )

    subtotal_company_currency = fields.Monetary(
        compute="_compute_subtotal_company_currency",
        currency_field="company_currency_id",
    )
    price_unit_company_currency = fields.Monetary(
        compute="_compute_price_unit_company_currency",
        currency_field="company_currency_id",
    )

    @api.depends(
        "l10n_ve_global_discount_line",
        "l10n_ve_global_discount_tax_ids",
        "account_id",
        "move_id",
        "currency_rate",
        "display_type",
    )
    def _compute_l10n_ve_global_discount_allocation_key(self):
        for line in self:
            if (
                line.l10n_ve_global_discount_line
                and line.display_type == "global_discount"
                and line.move_id
            ):
                line.l10n_ve_global_discount_allocation_key = frozendict(
                    {
                        "move_id": line.move_id.id,
                        "account_id": line.account_id.id,
                        "currency_rate": line.currency_rate,
                        "tax_ids": tuple(sorted(line.l10n_ve_global_discount_tax_ids.ids)),
                    }
                )
            else:
                line.l10n_ve_global_discount_allocation_key = False

    @api.depends(
        "l10n_ve_line_discount_line",
        "l10n_ve_global_discount_tax_ids",
        "account_id",
        "move_id",
        "currency_rate",
        "display_type",
    )
    def _compute_l10n_ve_line_discount_allocation_key(self):
        for line in self:
            if (
                line.l10n_ve_line_discount_line
                and line.display_type == "discount"
                and line.move_id
            ):
                line.l10n_ve_line_discount_allocation_key = frozendict(
                    {
                        "move_id": line.move_id.id,
                        "account_id": line.account_id.id,
                        "currency_rate": line.currency_rate,
                        "tax_ids": tuple(
                            sorted(line.l10n_ve_global_discount_tax_ids.ids)
                        ),
                    }
                )
            else:
                line.l10n_ve_line_discount_allocation_key = False

    @api.depends("account_id", "company_id")
    def _compute_discount_allocation_key(self):
        super()._compute_discount_allocation_key()
        for line in self.filtered(
            lambda aml: aml.l10n_ve_global_discount_line or aml.l10n_ve_line_discount_line
        ):
            line.discount_allocation_key = False

    @api.depends(
        "account_id",
        "company_id",
        "discount",
        "price_unit",
        "quantity",
        "currency_rate",
        "analytic_distribution",
    )
    def _compute_discount_allocation_needed(self):
        ve_journal_lines = self.filtered(
            lambda line: line.move_id._l10n_ve_uses_global_discount_journal_lines()
        )
        super(AccountMoveLine, self - ve_journal_lines)._compute_discount_allocation_needed()
        for line in ve_journal_lines:
            line.discount_allocation_needed = False
            line.discount_allocation_dirty = True

    @api.depends("balance")
    def _compute_subtotal_company_currency(self):
        for line in self:
            if line.move_id.move_type in ["out_invoice", "in_invoice"]:
                line.subtotal_company_currency = abs(line.balance)
                continue
            if line.move_id.move_type in ["out_refund", "in_refund"]:
                line.subtotal_company_currency = abs(line.balance)
                continue
            line.subtotal_company_currency = 0.0

    @api.depends("subtotal_company_currency", "discount", "quantity")
    def _compute_price_unit_company_currency(self):
        for line in self:
            qty = line.quantity or 0.0
            if not qty:
                line.price_unit_company_currency = 0.0
                continue
            discount_factor = 1 - ((line.discount or 0.0) / 100.0)
            if not discount_factor:
                line.price_unit_company_currency = 0.0
                continue
            subtotal_wo_discount = line.subtotal_company_currency / discount_factor
            line.price_unit_company_currency = subtotal_wo_discount / qty

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if self.env.context.get("l10n_ve_skip_exempt_tax_line"):
            return res
        for record in res:
            if record.move_id.move_type == "entry":
                continue

            if record.move_id.country_code != self.env.ref("base.ve").code:
                continue

            record._validate_line_unit_price_ve()
            record._l10n_ve_apply_exempt_tax_no_product_line()
            record._put_unique_tax_per_line()
        res._l10n_ve_refresh_move_global_discounts()
        return res

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("l10n_ve_skip_exempt_tax_line"):
            return res
        for record in self:
            if record.move_id.move_type == "entry":
                continue
            if record.move_id.country_code != self.env.ref("base.ve").code:
                continue
            if not record._l10n_ve_can_auto_update_tax_fields():
                continue

            if "price_unit" in vals or "quantity" in vals:
                record._validate_line_unit_price_ve()
            record._l10n_ve_apply_exempt_tax_no_product_line()
            record._put_unique_tax_per_line()
        if set(vals) & {
            "price_unit",
            "quantity",
            "discount",
            "tax_ids",
            "product_id",
            "display_type",
        }:
            self._l10n_ve_refresh_move_global_discounts()
        return res

    def unlink(self):
        moves = self.move_id
        res = super().unlink()
        moves._l10n_ve_refresh_global_discounts_from_lines()
        return res

    def _l10n_ve_refresh_move_global_discounts(self):
        if self.env.context.get("l10n_ve_skip_discount_refresh"):
            return
        product_lines = self.filtered(
            lambda line: line.display_type not in ("line_section", "line_note")
            and not line.tax_line_id
        )
        if product_lines:
            product_lines.move_id._l10n_ve_refresh_global_discounts_from_lines()

    def _validate_line_unit_price_ve(self):
        """Valida precio unitario distinto de cero en líneas fiscales venezolanas.

        Notes
        -----
        Art. 13 num. 8 PA SNAT/2011/0071: descripción y precio de la operación.
        """

        self.ensure_one()
        if self.move_id.move_type == "entry":
            return
        if self.move_id.country_code != "VE":
            return
        if self.display_type != "product":
            return
        prec = self.env["decimal.precision"].precision_get("Product Price")
        price = self.price_unit or 0.0
        if float_compare(price, 0.0, precision_digits=prec) <= 0:
            tmpl = self.product_id.product_tmpl_id if self.product_id else False
            if tmpl and tmpl._l10n_ve_is_sale_discount_template():
                return
            raise ValidationError(
                _(
                    "No se permiten líneas con precio menor o igual a cero. "
                    'La línea "%(line)s" tiene precio %(price)s. Use el producto de '
                    "descuento de la compañía (asistente Descuento en pedidos) o corrija "
                    "el importe."
                )
                % {"line": self.name or _("Sin nombre"), "price": price}
            )

    @api.constrains("discount", "move_id")
    def _l10n_ve_check_line_discount(self):
        prec = self.env["decimal.precision"].precision_get("Discount")
        for line in self:
            if line.display_type != "product":
                continue
            if line.move_id.move_type == "entry":
                continue
            if line.move_id.country_code != "VE":
                continue
            disc = line.discount or 0.0
            if float_compare(disc, 100.0, precision_digits=prec) >= 0:
                raise ValidationError(
                    _(
                        "No se permite un descuento del 100%% en la línea de factura. "
                        'La línea "%(line)s" tiene %(discount)s%%.'
                    )
                    % {
                        "line": line.name or _("Sin nombre"),
                        "discount": disc,
                    }
                )

    def l10n_ve_report_line_description(self):
        """Descripción de línea para reporte, marcando exentos con sufijo (E).

        Returns
        -------
        str

        Notes
        -----
        Art. 13 num. 8 PA SNAT/2011/0071: carácter (E) en operaciones exentas.
        Art. 7 num. 8 PA SNAT/2024/000102: mismo requisito en factura digital.
        """

        self.ensure_one()
        name = (self.name or "").strip()
        product = self.product_id
        if product:
            desc = (product.name or "").strip() or name
        else:
            desc = name
        if self._l10n_ve_line_is_exempt_for_report():
            desc = desc.rstrip()
            if not desc.endswith("(E)"):
                desc = f"{desc} (E)"
        return desc

    def _l10n_ve_line_is_exempt_for_report(self):
        self.ensure_one()
        if self.move_id.country_code != "VE":
            return False
        if self.display_type != "product":
            return False
        if not self.tax_ids:
            return False
        return all(
            float_compare(tax.amount, 0.0, precision_digits=4) == 0
            for tax in self.tax_ids
        )

    def _l10n_ve_must_use_exempt_tax(self):
        self.ensure_one()
        if self.env.context.get("l10n_ve_skip_exempt_tax_line"):
            return False
        if self.move_id.country_code != "VE":
            return False
        if not self.move_id.is_sale_document(include_receipts=True):
            return False
        if self.move_id.move_type not in (
            "out_invoice",
            "out_refund",
            "out_receipt",
        ):
            return False
        if self.display_type == "line_section":
            return False
        if self.display_type == "line_note":
            return True
        if self.display_type == "product" and not self.product_id:
            return True
        return False

    def _l10n_ve_can_auto_update_tax_fields(self):
        self.ensure_one()
        return self.parent_state != "posted"

    @api.depends(
        "product_id",
        "product_uom_id",
        "display_type",
        "move_id.move_type",
        "move_id.country_code",
        "move_id.company_id",
        "move_id.fiscal_position_id",
    )
    def _compute_tax_ids(self):
        super()._compute_tax_ids()
        for line in self:
            if not line.move_id:
                continue
            if not line._l10n_ve_can_auto_update_tax_fields():
                continue
            if not line._l10n_ve_must_use_exempt_tax():
                continue
            tax = line._l10n_ve_get_exempt_tax_for_line()
            if not tax:
                continue
            if line.move_id.fiscal_position_id:
                tax = line.move_id.fiscal_position_id.map_tax(tax)
            if tax:
                line.tax_ids = tax

    def _l10n_ve_get_exempt_tax_for_line(self):
        self.ensure_one()
        company = self.move_id.company_id
        ProductTemplate = self.env["product.template"]
        if self.move_id.is_sale_document(include_receipts=True):
            return ProductTemplate._l10n_ve_get_exent_sale_tax(company)
        return ProductTemplate._l10n_ve_get_exent_purchase_tax(company)

    def _l10n_ve_apply_exempt_tax_no_product_line(self):
        self.ensure_one()
        if self.env.context.get("l10n_ve_skip_exempt_tax_line"):
            return
        if not self._l10n_ve_can_auto_update_tax_fields():
            return
        if not self._l10n_ve_must_use_exempt_tax():
            return
        tax = self._l10n_ve_get_exempt_tax_for_line()
        if not tax:
            return
        if self.move_id.fiscal_position_id:
            tax = self.move_id.fiscal_position_id.map_tax(tax)
        if not tax:
            return
        if set(self.tax_ids.ids) == set(tax.ids):
            return
        self.with_context(l10n_ve_skip_exempt_tax_line=True).write(
            {"tax_ids": [Command.set(tax.ids)]}
        )

    def _put_unique_tax_per_line(self):
        """Impide más de un impuesto de venta por línea de factura.

        Notes
        -----
        Art. 13 num. 9-11 PA SNAT/2011/0071: discriminación de alícuota por línea.
        """

        self.ensure_one()
        if not self._l10n_ve_can_auto_update_tax_fields():
            return
        if self.display_type not in ("product", "discount"):
            return

        if len(self.tax_ids) == 0:
            if self.move_id.move_type in ("out_invoice", "out_refund", "out_receipt"):
                self.tax_ids = [Command.link(self.env.company.account_sale_tax_id.id)]
                self.move_id.message_post(
                    body=_("Added default sales tax to line: %s.") % self.name
                )

            if self.move_id.move_type in ("in_invoice", "in_refund", "in_receipt"):
                self.tax_ids = [
                    Command.link(self.env.company.account_purchase_tax_id.id)
                ]
