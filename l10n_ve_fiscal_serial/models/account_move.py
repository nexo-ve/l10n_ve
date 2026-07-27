import json
import re

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_fiscal_serial_reprint_document_type(self):
        self.ensure_one()
        if self.move_type == "out_refund":
            return "out_refund"
        if self.move_type == "out_invoice" and self.debit_origin_id:
            return "debit_note"
        return "out_invoice"

    def _l10n_ve_fiscal_serial_normalize_reprint_number(self, number):
        digits = re.sub(r"\D", "", str(number or ""))
        if not digits:
            return "0000000"
        return digits[-7:].zfill(7)

    def _l10n_ve_fiscal_serial_prepare_line_name_and_code(self, line):
        self.ensure_one()
        if line.product_id:
            base_name = line.product_id.name or line.name or ""
            default_code = line.product_id.default_code or ""
        else:
            base_name = line.name or ""
            default_code = ""

        if (
            self.company_id.l10n_ve_fiscal_serial_send_default_code_in_name
            and default_code
        ):
            return f"[{default_code}] {base_name}".strip(), ""
        return base_name, default_code

    def _l10n_ve_fiscal_serial_date_ddmmyyyy(self, value):
        date_value = fields.Date.to_date(value) if value else False
        if not date_value:
            return ""
        return date_value.strftime("%d/%m/%Y")

    def _l10n_ve_fiscal_serial_validate_print_base(self):
        self.ensure_one()
        if self.country_code != "VE":
            raise ValidationError(_("Esta acción solo aplica para compañías VE."))
        if self.l10n_ve_journal_emission_medium != "fiscal_machine":
            raise ValidationError(_("El diario no está configurado como máquina fiscal."))
        if not self.journal_id.l10n_ve_fiscal_machine_id:
            raise ValidationError(
                _("Configure la máquina fiscal en el diario de ventas.")
            )
        if self.state != "posted":
            raise ValidationError(_("Debe confirmar la factura antes de imprimirla fiscalmente."))

    def _l10n_ve_fiscal_serial_journal_machine_payload(self):
        self.ensure_one()
        if self.l10n_ve_journal_emission_medium != "fiscal_machine":
            return {}
        machine = self.journal_id.l10n_ve_fiscal_machine_id
        if not machine:
            raise ValidationError(
                _("Configure la máquina fiscal en el diario de ventas.")
            )
        baud = machine.baudrate or "9600"
        return {
            "machine_id": machine.id,
            "name": machine.name or "",
            "registered_serial": machine.registered_serial or "",
            "baudrate": int(baud) if str(baud).isdigit() else 9600,
            "parity": machine.parity
            if machine.parity in ("none", "even", "odd")
            else "even",
            "flag_21": machine.flag_21
            or self.company_id.l10n_ve_fiscal_serial_flag_21
            or "30",
            "serial_port": machine.serial_port or "",
            "webserial_usb_vendor_id": machine.webserial_usb_vendor_id or 0,
            "webserial_usb_product_id": machine.webserial_usb_product_id or 0,
            "webserial_usb_serial_number": machine.webserial_usb_serial_number or "",
        }

    def _l10n_ve_fiscal_serial_map_tax_code(self, line):
        tax = line.tax_ids[:1]
        if not tax:
            return "0"
        amount = abs(tax.amount)
        if amount <= 0:
            return "0"
        if amount <= 8:
            return "2"
        if amount <= 16:
            return "1"
        return "3"

    def _l10n_ve_fiscal_serial_line_price_unit_for_print(self, line):
        self.ensure_one()
        price = line.price_unit or 0.0
        if self.currency_id == self.company_currency_id:
            return price
        rate = line.currency_rate or self.invoice_currency_rate or 0.0
        if not float_is_zero(rate, precision_rounding=1e-9):
            return self.company_currency_id.round(price / rate)
        return price

    def _l10n_ve_fiscal_serial_global_discount_amount(self):
        self.ensure_one()
        tax_totals = self.tax_totals or {}
        amount = tax_totals.get("l10n_ve_global_discount_amount", 0.0)
        if float_is_zero(amount, precision_rounding=self.company_currency_id.rounding):
            return 0.0
        return amount

    def _l10n_ve_fiscal_serial_line_discount_amounts(self):
        self.ensure_one()
        base_lines, _tax_lines = self._get_rounded_base_and_tax_lines()
        return self.env["account.tax"]._l10n_ve_get_line_discount_amounts(
            base_lines,
            self.company_id,
        )

    def _l10n_ve_fiscal_serial_invoice_lines_payload(self):
        self.ensure_one()
        discount_amounts = self._l10n_ve_fiscal_serial_line_discount_amounts()
        lines = []
        for line in self.invoice_line_ids.filtered(
            lambda line_item: line_item.display_type in (False, "product")
        ):
            display_name, default_code = self._l10n_ve_fiscal_serial_prepare_line_name_and_code(line)
            lines.append(
                {
                    "tax": self._l10n_ve_fiscal_serial_map_tax_code(line),
                    "tax_percent": line.tax_ids[:1].amount if line.tax_ids[:1] else 0.0,
                    "price_unit": self._l10n_ve_fiscal_serial_line_price_unit_for_print(line),
                    "quantity": line.quantity,
                    "default_code": default_code,
                    "name": display_name,
                    "discount": line.discount or 0.0,
                    "discount_amount": discount_amounts.get(line.id, 0.0),
                }
            )
        return lines

    def _l10n_ve_fiscal_serial_journal_fiscal_payment_code(self, journal):
        if not journal:
            return "01"
        journal_code = getattr(journal, "l10n_ve_fiscal_payment_code", False)
        if journal_code:
            code = str(journal_code).strip()
            if code:
                return code.zfill(2)
        fallback = getattr(journal, "payment_method", False) or getattr(
            journal, "l10n_ve_payment_method", False
        )
        if fallback:
            return str(fallback).strip().zfill(2)
        return "01"

    def _l10n_ve_fiscal_serial_payment_lines_from_pos_orders(self):
        self.ensure_one()
        lines = []
        for order in self.pos_order_ids:
            conv_date = (
                fields.Date.to_date(order.date_order)
                if order.date_order
                else (self.invoice_date or self.date)
            )
            order_currency = order.currency_id
            for pay in order.payment_ids.sorted("id"):
                if pay.is_change:
                    continue
                if pay.payment_method_id.type == "pay_later":
                    continue
                amount = abs(float(pay.amount))
                if float_is_zero(amount, precision_rounding=order_currency.rounding):
                    continue
                amount_company = order_currency._convert(
                    amount,
                    self.company_currency_id,
                    self.company_id,
                    conv_date,
                )
                if float_is_zero(
                    amount_company,
                    precision_rounding=self.company_currency_id.rounding,
                ):
                    continue
                journal = pay.payment_method_id.journal_id
                lines.append(
                    {
                        "amount": amount_company,
                        "payment_method": self._l10n_ve_fiscal_serial_journal_fiscal_payment_code(
                            journal
                        ),
                    }
                )
        return lines

    def _l10n_ve_fiscal_serial_payment_lines_from_invoice_widget(self):
        self.ensure_one()
        lines = []
        payments_widget = self.invoice_payments_widget or {}
        if isinstance(payments_widget, bytes):
            try:
                payments_widget = json.loads(payments_widget.decode("utf-8"))
            except Exception:
                payments_widget = {}
        elif isinstance(payments_widget, str):
            try:
                payments_widget = json.loads(payments_widget)
            except Exception:
                payments_widget = {}

        reconciled = payments_widget.get("content", []) if isinstance(payments_widget, dict) else []

        for item in reconciled:
            if item.get("is_exchange"):
                continue
            amount = item.get("amount")
            if amount is None:
                continue
            amount = abs(float(amount))
            item_currency_id = item.get("currency_id")
            from_currency = self.currency_id
            if item_currency_id and item_currency_id != self.currency_id.id:
                from_currency = self.env["res.currency"].browse(item_currency_id)
            if float_is_zero(amount, precision_rounding=from_currency.rounding):
                continue
            conv_date = item.get("date")
            conv_date = fields.Date.to_date(conv_date) if conv_date else False
            if not conv_date:
                conv_date = self.invoice_date or self.date
            amount_company = from_currency._convert(
                amount,
                self.company_currency_id,
                self.company_id,
                conv_date,
            )
            if float_is_zero(
                amount_company,
                precision_rounding=self.company_currency_id.rounding,
            ):
                continue
            journal = False
            payment_id = item.get("account_payment_id")
            if payment_id:
                payment = self.env["account.payment"].browse(payment_id)
                journal = payment.journal_id
            else:
                counterpart_move = self.env["account.move"].browse(item.get("move_id"))
                journal = counterpart_move.journal_id
            payment_method = self._l10n_ve_fiscal_serial_journal_fiscal_payment_code(journal)
            lines.append(
                {
                    "amount": amount_company,
                    "payment_method": payment_method,
                }
            )
        return lines

    def _l10n_ve_fiscal_serial_fallback_payment_line(self):
        self.ensure_one()
        payment_method = "01"
        if self.l10n_ve_igtf_document_has_igtf():
            payment_method = "21"
        return {"amount": 0, "payment_method": payment_method}

    def _l10n_ve_fiscal_serial_payment_lines_payload(self):
        self.ensure_one()
        lines = []
        if "pos_order_ids" in self._fields and self.pos_order_ids:
            lines = self._l10n_ve_fiscal_serial_payment_lines_from_pos_orders()
        if not lines:
            lines = self._l10n_ve_fiscal_serial_payment_lines_from_invoice_widget()
        if not lines:
            lines.append(self._l10n_ve_fiscal_serial_fallback_payment_line())
        return lines

    def _l10n_ve_fiscal_serial_partner_payload(self):
        self.ensure_one()
        partner = self.partner_id
        return {
            "name": partner.name or "",
            "vat": partner.vat or "",
            "address": partner.street or "",
            "phone": partner.phone or partner.mobile or "",
        }

    def _l10n_ve_fiscal_serial_base_payload(self):
        self.ensure_one()
        machine_cfg = self._l10n_ve_fiscal_serial_journal_machine_payload()
        flag_21 = machine_cfg.get("flag_21") or (
            self.company_id.l10n_ve_fiscal_serial_flag_21 or "30"
        )
        return {
            "company_id": self.company_id.id,
            "partner_id": self._l10n_ve_fiscal_serial_partner_payload(),
            "invoice_lines": self._l10n_ve_fiscal_serial_invoice_lines_payload(),
            "payment_lines": self._l10n_ve_fiscal_serial_payment_lines_payload(),
            "global_discount_amount": self._l10n_ve_fiscal_serial_global_discount_amount(),
            "flag_21": flag_21,
            "fiscal_machine": machine_cfg or False,
            "aditional_lines": [],
            "has_cashbox": False,
            "use_emulator": bool(self.company_id.l10n_ve_fiscal_serial_use_emulator),
        }

    def check_print_out_invoice(self):
        self.ensure_one()
        self._l10n_ve_fiscal_serial_validate_print_base()
        if self.move_type != "out_invoice":
            raise ValidationError(_("Solo puede imprimir facturas de cliente."))
        if self.l10n_ve_invoice_number:
            raise ValidationError(_("La factura ya fue impresa en máquina fiscal."))
        payload = self._l10n_ve_fiscal_serial_base_payload()
        payload.update({"move_type": self.move_type, "move_id": self.id})
        return payload

    def check_print_out_refund(self):
        self.ensure_one()
        self._l10n_ve_fiscal_serial_validate_print_base()
        if self.move_type != "out_refund":
            raise ValidationError(_("Solo puede imprimir notas de crédito de cliente."))
        if self.l10n_ve_invoice_number:
            raise ValidationError(_("La nota de crédito ya fue impresa en máquina fiscal."))
        if not self.reversed_entry_id:
            raise ValidationError(_("La nota de crédito debe tener factura afectada."))
        if not self.reversed_entry_id.l10n_ve_invoice_number:
            raise ValidationError(
                _(
                    "La factura afectada no tiene número fiscal. "
                    "No se puede imprimir la nota de crédito."
                )
            )
        payload = self._l10n_ve_fiscal_serial_base_payload()
        payload.update(
            {
                "move_type": self.move_type,
                "move_id": self.id,
                "invoice_affected": {
                    "number": self.reversed_entry_id.l10n_ve_invoice_number,
                    "serial_machine": self.reversed_entry_id.l10n_ve_serial_number,
                    "date": self._l10n_ve_fiscal_serial_date_ddmmyyyy(
                        self.reversed_entry_id.invoice_date or self.reversed_entry_id.date
                    ),
                },
            }
        )
        return payload

    def check_print_debit_note(self):
        self.ensure_one()
        self._l10n_ve_fiscal_serial_validate_print_base()
        if self.move_type != "out_invoice" or not self.debit_origin_id:
            raise ValidationError(_("Solo puede imprimir notas de débito de cliente."))
        if self.l10n_ve_invoice_number:
            raise ValidationError(_("La nota de débito ya fue impresa en máquina fiscal."))
        if not self.debit_origin_id.l10n_ve_invoice_number:
            raise ValidationError(
                _(
                    "La factura origen no tiene número fiscal. "
                    "No se puede imprimir la nota de débito."
                )
            )
        payload = self._l10n_ve_fiscal_serial_base_payload()
        payload.update(
            {
                "move_type": self.move_type,
                "move_id": self.id,
                "invoice_affected": {
                    "number": self.debit_origin_id.l10n_ve_invoice_number,
                    "serial_machine": self.debit_origin_id.l10n_ve_serial_number,
                    "date": self._l10n_ve_fiscal_serial_date_ddmmyyyy(
                        self.debit_origin_id.invoice_date or self.debit_origin_id.date
                    ),
                },
            }
        )
        return payload

    def check_reprint(self):
        self.ensure_one()
        self._l10n_ve_fiscal_serial_validate_print_base()
        if not self.l10n_ve_invoice_number:
            raise ValidationError(_("El documento no tiene número fiscal para reimprimir."))
        return {
            "type": self.move_type,
            "reprint_document_type": self._l10n_ve_fiscal_serial_reprint_document_type(),
            "mf_number": self._l10n_ve_fiscal_serial_normalize_reprint_number(
                self.l10n_ve_invoice_number
            ),
            "move_id": self.id,
            "fiscal_machine": self._l10n_ve_fiscal_serial_journal_machine_payload(),
        }

    def _l10n_ve_fiscal_serial_write_print_result(self, values):
        self.ensure_one()
        data = values.get("data") if isinstance(values, dict) and values.get("data") else values
        if not isinstance(data, dict):
            raise ValidationError(_("Respuesta fiscal inválida."))
        vals = {}
        sequence = data.get("sequence")
        serial = data.get("serial_machine")
        report_z = data.get("mf_reportz") or data.get("report_z")
        if sequence:
            vals["l10n_ve_invoice_number"] = str(sequence)
        if serial:
            vals["l10n_ve_serial_number"] = str(serial)
        if report_z:
            vals["l10n_ve_report_z"] = str(report_z)
        vals["l10n_ve_invoice_date"] = fields.Datetime.now()
        if not self.l10n_ve_invoice_original_printed:
            vals["l10n_ve_invoice_original_printed"] = True
        self.write(vals)
        return True

    def print_out_invoice(self, values):
        self.ensure_one()
        return self._l10n_ve_fiscal_serial_write_print_result(values)

    def print_out_refund(self, values):
        self.ensure_one()
        return self._l10n_ve_fiscal_serial_write_print_result(values)

    def print_debit_note(self, values):
        self.ensure_one()
        return self._l10n_ve_fiscal_serial_write_print_result(values)
