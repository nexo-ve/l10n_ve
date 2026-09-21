# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _
from odoo.exceptions import ValidationError


def check_l10n_ve_pos_credit_invoice_currency(env, currency, company):
    """Shared FR-4 validation for the POS credit invoice currency, used by
    both `pos.config` and `res.company` (defect F8) so the rule is defined
    once.

    Scoped and run with `sudo()` (defect F2b): the previous, unscoped,
    non-sudo `search_count` both false-passed (it could see another
    company's exchange rates) and false-failed (record rules can hide the
    rates of a company the current user is not currently working in).
    `company_id IN (False, company.root_id.id)` matches the scoping
    `res.currency._get_rates` itself applies.
    """
    if not currency:
        return
    if not currency.active:
        raise ValidationError(
            _(
                "The POS credit invoice currency %(currency)s is archived. "
                "Activate it or choose a different currency.",
                currency=currency.display_name,
            )
        )
    has_rate = (
        env["res.currency.rate"]
        .sudo()
        .search_count(
            [
                ("currency_id", "=", currency.id),
                ("company_id", "in", (False, company.root_id.id)),
            ],
            limit=1,
        )
    )
    if not has_rate:
        raise ValidationError(
            _(
                "The POS credit invoice currency %(currency)s has no "
                "exchange rate defined for %(company)s. Add at least one "
                "rate before selecting it.",
                currency=currency.display_name,
                company=company.display_name,
            )
        )
