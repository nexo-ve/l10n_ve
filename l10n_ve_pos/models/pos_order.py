from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    invoice_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario de facturación",
        domain="[('type', '=', 'sale')]",
        check_company=True,
        help="Diario usado al facturar este pedido POS.",
    )
    l10n_ve_pos_invoice_name = fields.Char(
        related="account_move.name",
        string="Número de factura",
        readonly=True,
    )
    l10n_ve_pos_control_number = fields.Char(
        related="account_move.l10n_ve_control_number",
        string="N° de control SENIAT",
        readonly=True,
    )
    l10n_ve_pos_fiscal_invoice_number = fields.Char(
        related="account_move.l10n_ve_invoice_number",
        string="N° factura máquina fiscal",
        readonly=True,
    )
    l10n_ve_pos_fiscal_serial = fields.Char(
        related="account_move.l10n_ve_serial_number",
        string="Serial máquina fiscal",
        readonly=True,
    )
    l10n_ve_pos_fiscal_report_z = fields.Char(
        related="account_move.l10n_ve_report_z",
        string="N° reporte Z",
        readonly=True,
    )

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        if self.invoice_journal_id:
            vals["journal_id"] = self.invoice_journal_id.id
        return vals

    def _generate_pos_order_invoice(self):
        ve_orders = self.filtered(
            lambda order: order.company_id.account_fiscal_country_id.code == "VE"
        )
        other_orders = self - ve_orders

        result = False
        if other_orders:
            result = super(PosOrder, other_orders)._generate_pos_order_invoice()
        if ve_orders:
            result = super(
                PosOrder, ve_orders.with_context(generate_pdf=False)
            )._generate_pos_order_invoice()
        return result

    def _create_order_picking(self):
        self.ensure_one()
        if self.picking_ids:
            return
        if self.shipping_date:
            super()._create_order_picking()
            return
        if self._should_create_picking_real_time():
            picking_type = self.config_id.picking_type_id
            if self.partner_id.property_stock_customer:
                destination_id = self.partner_id.property_stock_customer.id
            elif not picking_type or not picking_type.default_location_dest_id:
                destination_id = self.env["stock.warehouse"]._get_partner_locations()[0].id
            else:
                destination_id = picking_type.default_location_dest_id.id

            pickings = self.env["stock.picking"].with_context(
                l10n_ve_pos_order_id=self.id
            )._create_picking_from_pos_order_lines(
                destination_id, self.lines, picking_type, self.partner_id
            )
            pickings.write(
                {
                    "pos_session_id": self.session_id.id,
                    "pos_order_id": self.id,
                    "origin": self.name,
                }
            )
