from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _l10n_ve_invoice_tag_include_igtf_notice(self):
        """Indica si la factura debe mostrar aviso de IGTF.

        Returns
        -------
        bool

        Notes
        -----
        Providencia SNAT/2022/000013: IGTF 3% en operaciones en divisas.
        """

        self.ensure_one()
        return bool(self.taxpayer_type and self.taxpayer_type != "ordinary")

    taxpayer_type = fields.Selection(
        related="partner_id.taxpayer_type",
        readonly=False,
    )
    l10n_ve_on_behalf_of_third_party_enabled = fields.Boolean(
        string="Facturación por cuenta de terceros habilitada",
        default=False,
    )
    l10n_ve_validate_partner_vat_format = fields.Boolean(
        string="Validar formato de RIF/CI",
        default=True,
    )
    l10n_ve_lock_partner_fiscal_data = fields.Boolean(
        string="Bloquear datos fiscales con movimientos",
        default=True,
    )
    l10n_ve_enforce_sale_price_ge_cost = fields.Boolean(
        string="Exigir precio de venta mayor o igual al coste",
        default=False,
    )
