# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountJournalFiscalMachine(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.groups_id |= cls.env.ref("l10n_ve_seniat.group_seniat")

    def _create_machine(self):
        return self.env["l10n.ve.fiscal.machine"].create(
            {
                "name": "HKA Journal Test",
                "company_id": self.env.company.id,
                "registered_serial": "JOURNALTEST1",
                "fiscal_rif": "J123456789",
            }
        )

    def test_fiscal_machine_required_on_fiscal_journal(self):
        journal = self.company_data["default_journal_sale"]
        machine = self._create_machine()
        with self.assertRaises(ValidationError):
            journal.write({"l10n_ve_emission_medium": "fiscal_machine"})
        journal.write(
            {
                "l10n_ve_emission_medium": "fiscal_machine",
                "l10n_ve_fiscal_machine_id": machine.id,
            }
        )
        self.assertEqual(journal.l10n_ve_fiscal_machine_id, machine)

    def test_fiscal_machine_cleared_when_changing_medium(self):
        journal = self.company_data["default_journal_sale"]
        machine = self._create_machine()
        journal.write(
            {
                "l10n_ve_emission_medium": "fiscal_machine",
                "l10n_ve_fiscal_machine_id": machine.id,
            }
        )
        journal.write({"l10n_ve_emission_medium": "digital"})
        self.assertFalse(journal.l10n_ve_fiscal_machine_id)

    def test_print_payload_uses_journal_machine(self):
        journal = self.company_data["default_journal_sale"]
        machine = self._create_machine()
        machine.write({"flag_21": "01", "baudrate": "19200", "parity": "none"})
        self._l10n_ve_configure_journal_fiscal_machine(
            journal,
            l10n_ve_fiscal_machine_id=machine.id,
            l10n_ve_invoice_section_id=False,
            l10n_ve_credit_note_section_id=False,
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente MF",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345670",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": journal.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Linea",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        },
                    )
                ],
            }
        )
        move.action_post()
        payload = move.check_print_out_invoice()
        self.assertEqual(payload["fiscal_machine"]["machine_id"], machine.id)
        self.assertEqual(payload["fiscal_machine"]["registered_serial"], "JOURNALTEST1")
        self.assertEqual(payload["fiscal_machine"]["baudrate"], 19200)
        self.assertEqual(payload["fiscal_machine"]["parity"], "none")
        self.assertEqual(payload["flag_21"], "01")
