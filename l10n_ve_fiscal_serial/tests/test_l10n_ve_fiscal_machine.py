# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeFiscalMachine(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("l10n_ve_seniat.group_seniat")

    def test_create_from_detect_payload(self):
        machine_model = self.env["l10n.ve.fiscal.machine"]
        payload = {
            "company_id": self.env.company.id,
            "name": "HKA 80 (ABC1234567)",
            "connection_type": "web_serial",
            "serial_port": "USB:2341-0043",
            "baudrate": "9600",
            "parity": "even",
            "data_bits": "8",
            "stop_bits": "1",
            "printer_type": "hka80",
            "printer_model_code": "Z1F",
            "printer_model_name": "SRP812",
            "country_code": "VE",
            "registered_serial": "ABC1234567",
            "fiscal_rif": "J123456789",
            "flag_21": "30",
            "last_invoice_number": "00000001",
            "enq_status": 64,
            "enq_error": 64,
            "enq_status_label": "Modo entrenamiento y en espera",
            "enq_error_label": "Sin error fiscal (STS2=0x40, manual TFHKA)",
            "s1_raw": "S1\n00000001\nABC1234567",
            "sv_raw": "SVZ1FVE",
        }
        machine_id = machine_model.create_from_detect_payload(payload)
        machine = machine_model.browse(machine_id)
        self.assertEqual(machine.registered_serial, "ABC1234567")
        self.assertEqual(machine.printer_model_name, "SRP812")
        self.assertEqual(machine.serial_port, "USB:2341-0043")

        machine_id_again = machine_model.create_from_detect_payload(payload)
        self.assertEqual(machine_id_again, machine.id)

    def test_apply_detect_result(self):
        wizard = self.env["l10n.ve.fiscal.machine.setup.wizard"].create(
            {"company_id": self.env.company.id}
        )
        wizard.apply_detect_result(
            {
                "detect_state": "done",
                "detect_message": "OK",
                "registered_serial": "XYZ9876543",
                "name": "HKA 80 (XYZ9876543)",
                "enq_status": 64,
                "enq_error": 64,
            }
        )
        self.assertEqual(wizard.detect_state, "done")
        self.assertEqual(wizard.registered_serial, "XYZ9876543")
        result = wizard.apply_detect_result(
            {
                "detect_state": "done",
                "detect_message": "OK",
                "registered_serial": "XYZ9876543",
                "name": "HKA 80 (XYZ9876543)",
                "enq_status": 64,
                "enq_error": 64,
                "serial_port": "USB:2341-0043",
            }
        )
        self.assertEqual(result["detect_state"], "done")
        self.assertEqual(result["serial_port"], "USB:2341-0043")
        self.assertIn("requires_manual_identification", result)
        result = wizard.apply_detect_result({"detect_message": "Actualizado"})
        self.assertEqual(result["detect_message"], "Actualizado")

    def test_apply_detect_result_preserves_manual_identification(self):
        wizard = self.env["l10n.ve.fiscal.machine.setup.wizard"].create(
            {
                "company_id": self.env.company.id,
                "registered_serial": "MANUAL123",
                "fiscal_rif": "J123456789",
            }
        )
        wizard.apply_detect_result(
            {
                "detect_state": "done",
                "enq_status": 64,
                "registered_serial": None,
                "fiscal_rif": None,
            }
        )
        self.assertEqual(wizard.registered_serial, "MANUAL123")
        self.assertEqual(wizard.fiscal_rif, "J123456789")
        self.assertFalse(wizard.requires_manual_identification)

        wizard.write({"fiscal_rif": False})
        self.assertTrue(wizard.requires_manual_identification)

    def test_action_open_setup_wizard(self):
        action = self.env["l10n.ve.fiscal.machine"].action_open_setup_wizard()
        self.assertEqual(action["res_model"], "l10n.ve.fiscal.machine.setup.wizard")
        self.assertEqual(action["target"], "new")
        self.assertTrue(action["res_id"])
        wizard = self.env["l10n.ve.fiscal.machine.setup.wizard"].browse(
            action["res_id"]
        )
        self.assertTrue(wizard.exists())
        self.assertEqual(wizard.company_id, self.env.company)
