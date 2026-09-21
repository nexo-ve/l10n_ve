# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from .l10n_ve_pos_credit_currency_validation import (
    check_l10n_ve_pos_credit_invoice_currency,
)


class PosConfig(models.Model):
    _inherit = "pos.config"

    # Deliberately a plain field, not `related`: the company value is only a
    # creation default (FR-2). Once a POS config has its own value, a later
    # per-POS override must not write back to the company, and a later change
    # to the company default must not silently change existing POS configs.
    l10n_ve_pos_credit_invoice_currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="POS Credit Invoice Currency",
        default=lambda self: self.env.company.l10n_ve_pos_credit_invoice_currency_id,
        help=(
            "Currency used to issue invoices for orders of this Point of Sale "
            "paid, in whole or in part, with a 'Customer Account' (pay later) "
            "payment method. Initialized from the company setting when this "
            "POS is created. Not shown in the POS UI and cannot be changed per "
            "order (FR-3). Leave empty to keep invoicing credit orders in the "
            "POS currency."
        ),
    )

    @api.constrains("l10n_ve_pos_credit_invoice_currency_id")
    def _check_l10n_ve_pos_credit_invoice_currency_id(self):
        for config in self:
            check_l10n_ve_pos_credit_invoice_currency(
                self.env,
                config.l10n_ve_pos_credit_invoice_currency_id,
                config.company_id,
            )
