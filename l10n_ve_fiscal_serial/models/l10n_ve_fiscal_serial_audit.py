# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class L10nVeFiscalSerialAudit(models.Model):
    _name = "l10n.ve.fiscal.serial.audit"
    _description = "Venezuela Fiscal Serial Audit Log"
    _order = "event_date desc, id desc"

    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Usuario",
        required=True,
        default=lambda self: self.env.uid,
        index=True,
    )
    machine_id = fields.Many2one(
        comodel_name="l10n.ve.fiscal.machine",
        string="Máquina fiscal",
        index=True,
        ondelete="set null",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Factura",
        index=True,
        ondelete="set null",
    )
    session_id = fields.Char(string="Sesión", index=True)
    event_date = fields.Datetime(
        string="Fecha",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    event_type = fields.Selection(
        selection=[
            ("port_open", "Apertura de puerto"),
            ("port_close", "Cierre de puerto"),
            ("command", "Comando / respuesta"),
        ],
        required=True,
        index=True,
    )
    source = fields.Selection(
        selection=[
            ("invoice_print", "Impresión de factura"),
            ("refund_print", "Impresión de nota de crédito"),
            ("debit_note", "Impresión de nota de débito"),
            ("reprint", "Reimpresión"),
            ("report", "Reporte X/Z"),
            ("machine_detect", "Detección de máquina"),
            ("debug_console", "Consola de depuración"),
            ("other", "Otro"),
        ],
        default="other",
        required=True,
        index=True,
    )
    serial_port = fields.Char(string="Puerto")
    webserial_usb_vendor_id = fields.Integer(string="USB Vendor ID")
    webserial_usb_product_id = fields.Integer(string="USB Product ID")
    webserial_usb_serial_number = fields.Char(string="USB Serial Number")
    baudrate = fields.Char(string="Baudios")
    parity = fields.Char(string="Paridad")
    duration_ms = fields.Integer(string="Duración (ms)")
    close_reason = fields.Selection(
        selection=[
            ("user_request", "Cierre solicitado por el usuario"),
            ("success", "Cierre tras operación exitosa"),
            ("error", "Cierre por error"),
            ("open_failed", "Fallo al abrir el puerto"),
            ("finally_cleanup", "Cierre de limpieza"),
            ("disconnect", "Desconexión del dispositivo"),
            ("cable", "Cable desconectado"),
            ("power_off", "Equipo apagado"),
            ("timeout", "Tiempo de espera agotado"),
            ("unknown", "Desconocido"),
        ],
        string="Motivo de cierre",
    )
    close_reason_detail = fields.Text(string="Detalle del cierre")
    command_step = fields.Char(string="Paso del comando")
    command_type = fields.Selection(
        selection=[
            ("enq", "ENQ"),
            ("framed", "Comando enmarcado"),
            ("status", "Estado (S1/SV/…)"),
            ("report", "Reporte"),
            ("ack", "ACK/NAK"),
            ("other", "Otro"),
        ],
        string="Tipo de comando",
    )
    command_payload = fields.Text(string="Comando enviado")
    response_payload = fields.Text(string="Respuesta recibida")
    response_summary = fields.Char(string="Resumen de respuesta")
    success = fields.Boolean(string="Éxito", default=True)
    error_message = fields.Text(string="Mensaje de error")

    _TEXT_LIMIT = 16000

    @api.model
    def _truncate_text(self, value):
        if value in (None, False, ""):
            return False
        text = str(value)
        if len(text) > self._TEXT_LIMIT:
            return f"{text[: self._TEXT_LIMIT]}…"
        return text

    @api.model
    def _prepare_event_vals(self, event):
        if not isinstance(event, dict):
            return {}
        event_type = event.get("event_type")
        if event_type not in {"port_open", "port_close", "command"}:
            return {}
        company_id = event.get("company_id") or self.env.company.id
        return {
            "company_id": company_id,
            "user_id": self.env.uid,
            "machine_id": event.get("machine_id") or False,
            "move_id": event.get("move_id") or False,
            "session_id": event.get("session_id") or False,
            "event_date": event.get("event_date") or fields.Datetime.now(),
            "event_type": event_type,
            "source": event.get("source") or "other",
            "serial_port": event.get("serial_port") or False,
            "webserial_usb_vendor_id": event.get("webserial_usb_vendor_id") or 0,
            "webserial_usb_product_id": event.get("webserial_usb_product_id") or 0,
            "webserial_usb_serial_number": event.get("webserial_usb_serial_number")
            or False,
            "baudrate": event.get("baudrate") and str(event.get("baudrate")) or False,
            "parity": event.get("parity") or False,
            "duration_ms": event.get("duration_ms") or 0,
            "close_reason": event.get("close_reason") or False,
            "close_reason_detail": self._truncate_text(
                event.get("close_reason_detail")
            ),
            "command_step": event.get("command_step") or False,
            "command_type": event.get("command_type") or False,
            "command_payload": self._truncate_text(event.get("command_payload")),
            "response_payload": self._truncate_text(event.get("response_payload")),
            "response_summary": event.get("response_summary") or False,
            "success": bool(event.get("success", True)),
            "error_message": self._truncate_text(event.get("error_message")),
        }

    @api.model
    def log_fiscal_serial_events(self, events):
        if not isinstance(events, list):
            events = [events]
        vals_list = []
        for event in events:
            vals = self._prepare_event_vals(event)
            if vals:
                vals_list.append(vals)
        if not vals_list:
            return []
        return self.create(vals_list).ids
