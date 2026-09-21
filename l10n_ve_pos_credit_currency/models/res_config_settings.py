# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_pos_credit_invoice_currency_id = fields.Many2one(
        related="pos_config_id.l10n_ve_pos_credit_invoice_currency_id",
        readonly=False,
        string="POS Credit Invoice Currency",
    )
    l10n_ve_company_pos_credit_invoice_currency_id = fields.Many2one(
        related="company_id.l10n_ve_pos_credit_invoice_currency_id",
        readonly=False,
        string="Company Default Credit Invoice Currency",
    )
