from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestL10nVeIgtfCommon


@tagged("post_install", "-at_install")
class TestIgtfCompanyConstraint(TestL10nVeIgtfCommon):
    """Cover res.company._check_l10n_ve_igtf_account_required_for_special.

    The constraint used to declare `partner_id.taxpayer_type` as a trigger
    field, which is not a valid `@api.constrains` dependency (constrains only
    accept direct field names of the model). Odoo silently ignored that
    dependency and logged a warning, so the constraint never fired when the
    taxpayer type changed. These tests exercise the fixed, direct
    `taxpayer_type` field name.
    """

    def test_setting_taxpayer_type_special_without_account_raises(self):
        """Switching a VE company to Special without an IGTF account raises."""
        self.company.write(
            {
                "l10n_ve_igtf_account_id": False,
                "taxpayer_type": "ordinary",
            }
        )

        with self.assertRaises(ValidationError):
            self.company.write({"taxpayer_type": "special"})

    def test_clearing_account_on_special_company_raises(self):
        """Clearing the IGTF account on a Special company raises."""
        self.assertEqual(self.company.taxpayer_type, "special")
        self.assertTrue(self.company.l10n_ve_igtf_account_id)

        with self.assertRaises(ValidationError):
            self.company.write({"l10n_ve_igtf_account_id": False})

    def test_special_company_with_account_saves_fine(self):
        """A Special company keeps saving fine once the account is set."""
        self.company.write(
            {
                "l10n_ve_igtf_account_id": False,
                "taxpayer_type": "ordinary",
            }
        )

        self.company.write(
            {
                "taxpayer_type": "special",
                "l10n_ve_igtf_account_id": self.igtf_account.id,
            }
        )

        self.assertEqual(self.company.taxpayer_type, "special")
        self.assertEqual(self.company.l10n_ve_igtf_account_id, self.igtf_account)

    def test_non_special_company_without_account_saves_fine(self):
        """A non-Special company never requires the IGTF account."""
        self.company.write(
            {
                "l10n_ve_igtf_account_id": False,
                "taxpayer_type": "ordinary",
            }
        )

        self.assertFalse(self.company.l10n_ve_igtf_feature_active)
        self.assertFalse(self.company.l10n_ve_igtf_account_id)
