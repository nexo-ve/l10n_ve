from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _load_pos_data_models(self, config_id):
        models_list = super()._load_pos_data_models(config_id)
        if "account.journal" not in models_list:
            if "account.fiscal.position" in models_list:
                index = models_list.index("account.fiscal.position")
                models_list.insert(index, "account.journal")
            else:
                models_list.append("account.journal")
        return models_list
