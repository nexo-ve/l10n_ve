# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _l10n_ve_pos_credit_currency_ensure_rate(self, currency, company, date):
        """Raise a clear error instead of ever posting a 1:1 invoice.

        VERIFIED IN CORE: `res.currency._get_rates` (base/models/res_currency.py)
        computes `COALESCE(rate_at_or_before_date, earliest_rate_ever, 1.0)`,
        filtered to `company_id IN (False, company.root_id.id)`. When no rate
        row is visible for this company at all, it silently returns 1.0, and
        `account.move._check_invoice_currency_rate` only rejects rate <= 0 -
        nothing else stops a foreign-currency invoice from posting at 1:1.
        This is a defense-in-depth check: FR-4 validates the POS config's
        currency at save time, but a rate row can still be deleted afterward.
        """
        has_rate = (
            self.env["res.currency.rate"]
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
            raise UserError(
                _(
                    "No exchange rate is defined for %(currency)s for "
                    "%(company)s. Add at least one exchange rate before "
                    "invoicing this order on credit, so it is never posted "
                    "at a 1:1 rate by mistake.",
                    currency=currency.display_name,
                    company=company.display_name,
                )
            )

    def _l10n_ve_pos_credit_currency_refund_target(self):
        """Currency and rates to reuse when this order refunds an order
        whose invoice currency differs from the order currency (PRD FR-13).

        Must be called on a single order: the len(self) > 1 guard in
        `_l10n_ve_pos_credit_currency_resolve()` always runs first, so a
        multi-order consolidated group never reaches this method. It is
        written defensively regardless, scanning only `self.lines` so one
        order's refund target can never leak onto another order.

        If this order's lines refund lines from invoices posted at
        different currencies or rates, raises a clear error instead of
        silently taking the first match.

        :return: (res.currency, price_rate, invoice_currency_rate) or
            (empty res.currency, 0.0, 0.0).
        """
        self.ensure_one()
        targets = {}
        for line in self.lines:
            origin_move = line.refunded_orderline_id.order_id.account_move
            if not origin_move or origin_move.currency_id == self.currency_id:
                continue
            key = (origin_move.currency_id.id, origin_move.invoice_currency_rate)
            targets[key] = origin_move

        if not targets:
            return self.env["res.currency"], 0.0, 0.0

        if len(targets) > 1:
            raise UserError(
                _(
                    "This refund's lines originate from invoices posted in "
                    "different currencies or at different exchange rates. "
                    "Refund them separately so each credit note reuses the "
                    "right original rate."
                )
            )

        (origin_move,) = targets.values()
        # `origin_move.invoice_currency_rate` is a company_currency ->
        # document_currency rate (core's own definition). Reusing it to
        # convert this order's line prices (expressed in `order.currency_id`,
        # see FR-6/defect F4) is only valid when the order currency equals
        # the company currency. There is no parallel rate source to derive
        # an order_currency -> credit_currency rate consistent with the
        # original invoice otherwise (PRD design constraint), so block
        # instead of silently reusing a rate that does not apply.
        if self.currency_id != self.company_id.currency_id:
            raise UserError(
                _(
                    "This order's currency differs from the company "
                    "currency, so the original invoice's exchange rate "
                    "cannot be safely reused to convert this refund's line "
                    "prices. Refund it manually."
                )
            )
        rate = origin_move.invoice_currency_rate
        return origin_move.currency_id, rate, rate

    def _l10n_ve_pos_credit_currency_credit_target(self):
        """Currency and rates to use when this order is on credit and its
        POS config defines a credit invoice currency (PRD FR-5/FR-6/FR-7).

        "On credit" (FR-5): at least one payment uses a payment method of
        type 'pay_later'. Only the standard rate table is used, at the
        order date, per PRD design constraints (no parallel rate source).

        Returns two separate rates (defect F4): `price_rate` converts line
        prices, which are expressed in `order.currency_id` (`pos.config
        .currency_id`, i.e. `journal_id.currency_id or company.currency_id`).
        `invoice_currency_rate` is the company_currency -> credit_currency
        rate that `account.move.invoice_currency_rate` requires by
        definition. They coincide when the POS currency equals the company
        currency (the normal Venezuelan case).

        :return: (res.currency, price_rate, invoice_currency_rate) or
            (empty res.currency, 0.0, 0.0).
        """
        for order in self:
            config = order.config_id
            credit_currency = config.l10n_ve_pos_credit_invoice_currency_id
            if not credit_currency or credit_currency == order.currency_id:
                # BR-1: a credit currency equal to the order's own currency
                # changes nothing.
                continue
            is_on_credit = any(
                payment.payment_method_id.type == "pay_later"
                for payment in order.payment_ids
            )
            if not is_on_credit:
                continue
            company = order.company_id
            # Company/user timezone, matching how core computes
            # `invoice_date` (`invoice_date.astimezone(timezone).date()` in
            # `pos.order._prepare_invoice_vals`), so the rate date always
            # matches the invoice date (PRD FR-7/BR-3/AC-6). `date_order` is
            # a naive UTC datetime, exactly like the `invoice_date` core
            # converts there.
            rate_date = order.date_order.astimezone(self.env.tz).date()
            order._l10n_ve_pos_credit_currency_ensure_rate(
                credit_currency, company, rate_date
            )
            Currency = self.env["res.currency"]
            price_rate = Currency._get_conversion_rate(
                order.currency_id, credit_currency, company, rate_date
            )
            if order.currency_id == company.currency_id:
                invoice_currency_rate = price_rate
            else:
                invoice_currency_rate = Currency._get_conversion_rate(
                    company.currency_id, credit_currency, company, rate_date
                )
            return credit_currency, price_rate, invoice_currency_rate
        return self.env["res.currency"], 0.0, 0.0

    def _l10n_ve_pos_credit_currency_resolve(self):
        """Resolve the (currency, price_rate, invoice_currency_rate) to
        apply to the invoice of this recordset, or (empty res.currency,
        0.0, 0.0) when the default POS-currency behavior applies.

        The `len(self) > 1` guard (BR-4, defect F5) always runs FIRST, for
        every branch: `l10n_ve_pos._prepare_invoice_vals()` (called by
        `super()` afterwards) calls `_l10n_ve_pos_refund_origin_journal()`,
        which does an unconditional `ensure_one()` and would otherwise raise
        a raw "Expected singleton" `ValueError` on any multi-order invoice,
        credit or not. PRD BR-4's stated default is "block with a clear
        error", so every multi-order group is blocked here, with the most
        specific message available for why.
        """
        if len(self) > 1:
            targets = [
                order._l10n_ve_pos_credit_currency_credit_target() for order in self
            ]
            is_credit = [bool(currency) for currency, *_rates in targets]
            if any(is_credit) and not all(is_credit):
                raise UserError(
                    _(
                        "This group mixes orders to be invoiced on credit "
                        "with orders that are not. Invoice them separately."
                    )
                )
            if all(is_credit):
                currencies = {currency for currency, *_rates in targets}
                rates = {
                    (price_rate, invoice_rate)
                    for _currency, price_rate, invoice_rate in targets
                }
                if len(currencies) > 1 or len(rates) > 1:
                    raise UserError(
                        _(
                            "These orders would be invoiced on credit at "
                            "different exchange rates. Invoice them "
                            "separately so each one uses its own daily rate."
                        )
                    )
            raise UserError(
                _(
                    "Multiple POS orders cannot be invoiced together in a "
                    "single consolidated invoice by this module. Invoice "
                    "each order separately."
                )
            )

        refund_currency, refund_price_rate, refund_invoice_rate = (
            self._l10n_ve_pos_credit_currency_refund_target()
        )
        if refund_currency:
            return refund_currency, refund_price_rate, refund_invoice_rate

        return self._l10n_ve_pos_credit_currency_credit_target()

    def _prepare_invoice_vals(self):
        # Resolve BEFORE calling `super()`. The BR-4 guard inside
        # `_l10n_ve_pos_credit_currency_resolve()` must reject an invalid
        # consolidated group with its own clear message before the rest of
        # the override chain runs: `l10n_ve_pos._prepare_invoice_vals()`
        # calls `_l10n_ve_pos_refund_origin_journal()`, which does an
        # unconditional `ensure_one()` and would otherwise raise a raw
        # "Expected singleton" ValueError first on any multi-order invoice.
        currency, price_rate, invoice_currency_rate = (
            self._l10n_ve_pos_credit_currency_resolve()
        )

        vals = super()._prepare_invoice_vals()
        if not currency:
            return vals

        vals["currency_id"] = currency.id
        vals["invoice_currency_rate"] = invoice_currency_rate

        for command in vals.get("invoice_line_ids") or []:
            line_vals = command[2] if len(command) > 2 else None
            if not line_vals or "price_unit" not in line_vals:
                # Section/note lines and combo lines carry no price_unit;
                # nothing to convert on them.
                continue
            # `account.move.line.price_unit` is declared with
            # `min_display_digits='Product Price'` and no `digits`
            # (account_move_line.py), so `Float.__init__` sets `digits =
            # False` (odoo/orm/fields_numeric.py): the column stores FULL
            # float precision and 2-decimal display is handled entirely by
            # `min_display_digits`. Rounding here would throw away
            # precision the ORM deliberately keeps, and the resulting error
            # is multiplied by quantity - this is defect F1. Multiply
            # without rounding so the invoice's company-currency total
            # (FR-10) reproduces the POS order total exactly.
            line_vals["price_unit"] = line_vals["price_unit"] * price_rate
            # `extra_tax_data` only carries data when the base line has a
            # manual tax override (down payments, combos, global discounts):
            # `_get_invoice_lines_values` builds it from
            # `_export_base_line_extra_tax_data`, which only populates the
            # dict when `manual_total_excluded[_currency]`/`manual_tax_amounts`
            # are set on the base line. Plain POS order lines never set those
            # (`pos.order.line._prepare_tax_base_line_values` calls
            # `_prepare_base_line_for_taxes_computation` with no manual_*
            # kwargs, and `pos.order.line` has no `extra_tax_data` field to
            # fall back to), so this key is `{}` for ordinary POS lines and
            # this rewrite is a no-op today. We still drop it defensively:
            # if another module ever populates it, it stores absolute
            # amounts and a `price_unit` in the POS currency, and the import
            # guard in `_import_base_line_extra_tax_data` would silently
            # ignore a stale entry anyway once price_unit/currency_id no
            # longer match, since it must match by value.
            line_vals.pop("extra_tax_data", None)

        # Do NOT pop `invoice_cash_rounding_id` (former defect F9): core's
        # own rounding-adjustment branch in `_create_invoice`/
        # `_recompute_cash_rounding_lines` already uses
        # `invoice.invoice_currency_rate` to convert the residual, so it
        # works correctly in a foreign credit currency. Removing the key
        # disabled that branch entirely, leaving cash-rounding POS orders
        # with an unexplained residual on the invoice (PRD FR-10 requires
        # residual rounding to go through the standard rounding handling).

        return vals
