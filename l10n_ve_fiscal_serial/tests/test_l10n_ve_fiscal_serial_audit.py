# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeFiscalSerialAudit(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("l10n_ve_seniat.group_seniat")

    def test_log_fiscal_serial_events(self):
        audit_model = self.env["l10n.ve.fiscal.serial.audit"]
        machine = self.env["l10n.ve.fiscal.machine"].create(
            {
                "name": "HKA 80",
                "registered_serial": "AUDIT123",
                "company_id": self.env.company.id,
            }
        )
        ids = audit_model.log_fiscal_serial_events(
            [
                {
                    "event_type": "port_open",
                    "source": "machine_detect",
                    "session_id": "sess-001",
                    "machine_id": machine.id,
                    "serial_port": "USB:1234-5678",
                    "baudrate": "9600",
                    "parity": "even",
                    "success": True,
                },
                {
                    "event_type": "command",
                    "source": "machine_detect",
                    "session_id": "sess-001",
                    "machine_id": machine.id,
                    "command_step": "SEND_CMD_REQUEST",
                    "command_type": "framed",
                    "command_payload": "iF",
                    "response_summary": "ACK",
                    "success": True,
                },
                {
                    "event_type": "port_close",
                    "source": "machine_detect",
                    "session_id": "sess-001",
                    "machine_id": machine.id,
                    "close_reason": "success",
                    "close_reason_detail": "Detección completada.",
                    "duration_ms": 1500,
                    "success": True,
                },
            ]
        )
        self.assertEqual(len(ids), 3)
        audits = audit_model.browse(ids)
        self.assertEqual(audits[0].event_type, "port_open")
        self.assertEqual(audits[0].user_id, self.env.user)
        self.assertEqual(audits[1].command_payload, "iF")
        self.assertEqual(audits[2].close_reason, "success")
        self.assertEqual(machine.audit_count, 3)

    def test_log_fiscal_serial_events_truncates_payload(self):
        audit_model = self.env["l10n.ve.fiscal.serial.audit"]
        long_text = "X" * 20000
        ids = audit_model.log_fiscal_serial_events(
            [
                {
                    "event_type": "command",
                    "source": "debug_console",
                    "command_payload": long_text,
                }
            ]
        )
        audit = audit_model.browse(ids[0])
        self.assertTrue(audit.command_payload.endswith("…"))
        self.assertLessEqual(len(audit.command_payload), 16001)
