from odoo import models


class ValidateAccountMove(models.TransientModel):
    _inherit = "validate.account.move"

    def validate_move(self):
        res = super().validate_move()
        self.move_ids._l10n_ve_create_post_retentions()
        return res
