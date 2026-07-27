# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AuditlogLog(models.Model):
    _inherit = "auditlog.log"

    is_fiscal_event = fields.Boolean(
        string="Fiscal Event",
        compute="_compute_is_fiscal_event",
        store=True,
        index=True,
    )
    fiscal_event_type = fields.Selection(
        selection=[
            ("draft_invoice", "Draft invoice"),
            ("draft_invoice_from_order", "Draft invoice from sale order"),
            ("draft_credit_note", "Draft credit note"),
            ("draft_debit_note", "Draft debit note"),
            ("invoice_posted", "Invoice posted"),
            ("credit_note_posted", "Credit note posted"),
            ("debit_note_posted", "Debit note posted"),
            ("fiscal_print", "Fiscal machine print"),
            ("edi_dispatch", "Digital dispatch"),
            ("document_cancelled", "Document cancelled"),
            ("retention_draft", "Retention draft"),
            ("retention_emitted", "Retention emitted"),
            ("retention_edi", "Retention digital dispatch"),
            ("dispatch_guide", "Dispatch guide"),
        ],
        readonly=True,
        index=True,
    )
    fiscal_event_description = fields.Text(
        string="Event Description",
        readonly=True,
    )

    @api.depends("method", "fiscal_event_type", "fiscal_event_description")
    def _compute_is_fiscal_event(self):
        for record in self:
            record.is_fiscal_event = bool(
                record.method == "fiscal_event"
                or record.fiscal_event_type
                or record.fiscal_event_description
            )

    @api.model
    def log_fiscal_event(self, record, event_type, description):
        record.ensure_one()
        model = self.env["ir.model"]._get(record._name)
        http_request = self.env["auditlog.http.request"].sudo()
        http_session = self.env["auditlog.http.session"].sudo()
        return self.sudo().create(
            {
                "model_id": model.id,
                "model_name": model.name,
                "model_model": model.model,
                "res_id": record.id,
                "name": (record.display_name or "")[:64],
                "user_id": self.env.uid,
                "method": "fiscal_event",
                "fiscal_event_type": event_type,
                "fiscal_event_description": description,
                "http_request_id": http_request.current_http_request(),
                "http_session_id": http_session.current_http_session(),
            }
        )
