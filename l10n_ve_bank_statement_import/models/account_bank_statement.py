# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError


class AccountBankStatement(models.Model):
    _inherit = "account.bank.statement"

    def unlink(self):
        for statement in self:
            reconciled_lines = statement.line_ids.filtered("is_reconciled")
            if reconciled_lines:
                raise UserError(
                    self.env._(
                        "No puede eliminar el estado de cuenta '%(statement)s' "
                        "porque tiene %(count)s apunte(s) conciliado(s).",
                        statement=statement.display_name,
                        count=len(reconciled_lines),
                    )
                )
        lines = self.mapped("line_ids")
        if lines:
            lines.unlink()
        return super().unlink()
