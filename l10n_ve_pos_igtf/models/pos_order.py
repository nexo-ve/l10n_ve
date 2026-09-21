from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    igtf_amount = fields.Float(string="IGTF")
    bi_igtf = fields.Float(string="Base IGTF")

    @api.model
    def _load_pos_data_fields(self, config):
        fields_list = super()._load_pos_data_fields(config)
        # An empty list means "load every field" (record.read([]) reads all
        # stored fields in the ORM), which already includes igtf_amount/
        # bi_igtf; only append when some other override narrowed the list to
        # an explicit subset (matching l10n_ve_pos/models/pos_order.py's own
        # convention for this same model).
        if not fields_list:
            return fields_list
        for field_name in ("igtf_amount", "bi_igtf"):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

