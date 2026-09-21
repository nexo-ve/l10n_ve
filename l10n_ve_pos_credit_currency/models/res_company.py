# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from .l10n_ve_pos_credit_currency_validation import (
    check_l10n_ve_pos_credit_invoice_currency,
)


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_pos_credit_invoice_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="POS Credit Invoice Currency",
        help=(
            "Currency used to issue invoices for Point of Sale orders paid, in "
            "whole or in part, with a 'Customer Account' (pay later) payment "
            "method. New POS configs use this value as their default; leave "
            "empty to keep invoicing credit orders in the POS currency, which "
            "is the current behavior."
        ),
    )

    @api.constrains("l10n_ve_pos_credit_invoice_currency_id")
    def _check_l10n_ve_pos_credit_invoice_currency_id(self):
        # Shared with `pos.config` (defect F8): without this, an admin could
        # save an archived or rate-less currency as the company default, and
        # every new POS config would silently inherit it through the field
        # default, only to fail `pos.config`'s own constraint at POS
        # creation time with a message that does not point at the company
        # setting that actually caused it.
        for company in self:
            check_l10n_ve_pos_credit_invoice_currency(
                self.env,
                company.l10n_ve_pos_credit_invoice_currency_id,
                company,
            )
