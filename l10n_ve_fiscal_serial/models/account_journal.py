from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_fiscal_machine_id = fields.Many2one(
        comodel_name="l10n.ve.fiscal.machine",
        string="Máquina fiscal",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id), ('active', '=', True)]",
        help="Máquina fiscal TFHKA asociada a este diario de ventas.",
    )

    @api.onchange("l10n_ve_emission_medium")
    def _onchange_l10n_ve_emission_medium_fiscal_machine(self):
        if self.l10n_ve_emission_medium != "fiscal_machine":
            self.l10n_ve_fiscal_machine_id = False

    def write(self, vals):
        if (
            "l10n_ve_emission_medium" in vals
            and vals["l10n_ve_emission_medium"] != "fiscal_machine"
        ):
            vals["l10n_ve_fiscal_machine_id"] = False
        return super().write(vals)

    @api.constrains(
        "l10n_ve_emission_medium",
        "l10n_ve_fiscal_machine_id",
        "company_id",
    )
    def _check_l10n_ve_fiscal_machine_id(self):
        for journal in self:
            machine = journal.l10n_ve_fiscal_machine_id
            if journal.l10n_ve_emission_medium == "fiscal_machine":
                if not machine:
                    raise ValidationError(
                        _(
                            "Debe seleccionar la máquina fiscal para el diario "
                            "«%(journal)s»."
                        )
                        % {"journal": journal.display_name}
                    )
            elif machine:
                raise ValidationError(
                    _(
                        "La máquina fiscal solo puede asignarse cuando el medio de "
                        "emisión del diario «%(journal)s» es «Máquina fiscal»."
                    )
                    % {"journal": journal.display_name}
                )
            if machine and machine.company_id != journal.company_id:
                raise ValidationError(
                    _(
                        "La máquina fiscal «%(machine)s» pertenece a otra compañía "
                        "que el diario «%(journal)s»."
                    )
                    % {
                        "machine": machine.display_name,
                        "journal": journal.display_name,
                    }
                )
