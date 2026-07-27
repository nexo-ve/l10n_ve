# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class L10nVeFiscalMachine(models.Model):
    _name = "l10n.ve.fiscal.machine"
    _description = "Venezuela Fiscal Machine"
    _order = "name, id"

    name = fields.Char(required=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)
    connection_type = fields.Selection(
        selection=[
            ("web_serial", "Web Serial (navegador)"),
        ],
        string="Tipo de conexión",
        required=True,
        default="web_serial",
    )
    serial_port = fields.Char(
        string="Puerto de conexión",
        help="Identificador del puerto serie o adaptador USB detectado.",
    )
    baudrate = fields.Selection(
        selection=[
            ("9600", "9600"),
            ("19200", "19200"),
            ("38400", "38400"),
            ("57600", "57600"),
            ("115200", "115200"),
        ],
        default="9600",
        required=True,
    )
    parity = fields.Selection(
        selection=[
            ("none", "Ninguna"),
            ("even", "Par"),
            ("odd", "Impar"),
        ],
        default="even",
        required=True,
    )
    data_bits = fields.Selection(
        selection=[("7", "7"), ("8", "8")],
        default="8",
        required=True,
    )
    stop_bits = fields.Selection(
        selection=[("1", "1"), ("2", "2")],
        default="1",
        required=True,
    )
    webserial_usb_vendor_id = fields.Integer(string="USB Vendor ID")
    webserial_usb_product_id = fields.Integer(string="USB Product ID")
    webserial_usb_serial_number = fields.Char(string="USB Serial Number")
    printer_type = fields.Selection(
        selection=[
            ("hka80", "HKA 80"),
            ("vmax801", "VMAX801"),
            ("other", "Otro"),
        ],
        string="Tipo de impresora",
        default="hka80",
        required=True,
    )
    printer_model_code = fields.Char(string="Código de modelo")
    printer_model_name = fields.Char(string="Modelo")
    country_code = fields.Char(string="País")
    registered_serial = fields.Char(string="Serial fiscal")
    fiscal_rif = fields.Char(string="RIF fiscal")
    flag_21 = fields.Selection(
        selection=[
            ("00", "00"),
            ("01", "01"),
            ("02", "02"),
            ("11", "11"),
            ("12", "12"),
            ("30", "30"),
        ],
        default="00",
        required=True,
    )
    last_invoice_number = fields.Char(readonly=True)
    last_credit_note_number = fields.Char(readonly=True)
    daily_closure_counter = fields.Char(readonly=True)
    enq_status = fields.Integer(string="ENQ STS1", readonly=True)
    enq_error = fields.Integer(string="ENQ STS2", readonly=True)
    enq_status_label = fields.Char(readonly=True)
    enq_error_label = fields.Char(readonly=True)
    last_connection = fields.Datetime(readonly=True)
    s1_raw = fields.Text(readonly=True)
    sv_raw = fields.Text(readonly=True)
    audit_count = fields.Integer(compute="_compute_audit_count")

    _sql_constraints = [
        (
            "registered_serial_company_uniq",
            "unique(registered_serial, company_id)",
            "Ya existe una máquina fiscal con este serial en la compañía.",
        ),
    ]

    def _compute_audit_count(self):
        audit_model = self.env["l10n.ve.fiscal.serial.audit"]
        machine_ids = self.ids
        counts = {
            machine.id: 0
            for machine in self
        }
        if machine_ids:
            for machine_id, count in audit_model._read_group(
                [("machine_id", "in", machine_ids)],
                groupby=["machine_id"],
                aggregates=["__count"],
            ):
                if machine_id:
                    counts[machine_id.id] = count
        for machine in self:
            machine.audit_count = counts.get(machine.id, 0)

    @api.model
    def create_from_detect_payload(self, payload):
        if not isinstance(payload, dict):
            raise ValidationError(_("Payload de detección inválido."))
        vals = self._prepare_vals_from_detect_payload(payload)
        if not vals.get("registered_serial"):
            raise ValidationError(
                _("No se pudo leer el serial fiscal (S1). Verifique la conexión.")
            )
        existing = self.search(
            [
                ("company_id", "=", vals["company_id"]),
                ("registered_serial", "=", vals["registered_serial"]),
            ],
            limit=1,
        )
        if existing:
            existing.write(vals)
            return existing.id
        return self.create(vals).id

    @api.model
    def _prepare_vals_from_detect_payload(self, payload):
        company_id = payload.get("company_id") or self.env.company.id
        registered_serial = (payload.get("registered_serial") or "").strip()
        printer_model_name = (payload.get("printer_model_name") or "").strip()
        name = (payload.get("name") or "").strip()
        if not name:
            if registered_serial and printer_model_name:
                name = f"{printer_model_name} ({registered_serial})"
            elif registered_serial:
                name = registered_serial
            else:
                name = payload.get("serial_port") or _("Máquina fiscal")
        return {
            "name": name,
            "company_id": company_id,
            "connection_type": payload.get("connection_type") or "web_serial",
            "serial_port": payload.get("serial_port"),
            "baudrate": payload.get("baudrate") or "9600",
            "parity": payload.get("parity") or "even",
            "data_bits": payload.get("data_bits") or "8",
            "stop_bits": payload.get("stop_bits") or "1",
            "webserial_usb_vendor_id": payload.get("webserial_usb_vendor_id") or 0,
            "webserial_usb_product_id": payload.get("webserial_usb_product_id") or 0,
            "webserial_usb_serial_number": payload.get("webserial_usb_serial_number"),
            "printer_type": payload.get("printer_type") or "hka80",
            "printer_model_code": payload.get("printer_model_code"),
            "printer_model_name": printer_model_name or None,
            "country_code": payload.get("country_code"),
            "registered_serial": registered_serial,
            "fiscal_rif": payload.get("fiscal_rif"),
            "flag_21": payload.get("flag_21") or "00",
            "last_invoice_number": payload.get("last_invoice_number"),
            "last_credit_note_number": payload.get("last_credit_note_number"),
            "daily_closure_counter": payload.get("daily_closure_counter"),
            "enq_status": payload.get("enq_status"),
            "enq_error": payload.get("enq_error"),
            "enq_status_label": payload.get("enq_status_label"),
            "enq_error_label": payload.get("enq_error_label"),
            "last_connection": fields.Datetime.now(),
            "s1_raw": payload.get("s1_raw"),
            "sv_raw": payload.get("sv_raw"),
        }

    def action_open_setup_wizard(self):
        wizard = self.env["l10n.ve.fiscal.machine.setup.wizard"].create(
            {"company_id": self.env.company.id}
        )
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_ve_fiscal_serial.action_l10n_ve_fiscal_machine_setup_wizard"
        )
        action["res_id"] = wizard.id
        return action

    def action_view_serial_audit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Auditoría fiscal serial"),
            "res_model": "l10n.ve.fiscal.serial.audit",
            "view_mode": "list,form",
            "domain": [("machine_id", "=", self.id)],
            "context": {"default_machine_id": self.id},
        }
