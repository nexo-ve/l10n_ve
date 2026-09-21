import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { floatIsZero, roundPrecision } from "@web/core/utils/numbers";

// Odoo 19 removed the order-level `taxTotals` getter; every total (priceIncl,
// totalDue, the receipt, ...) now reads `order.prices.taxDetails` instead.
// `prices` itself is defined on the parent class PosOrderAccounting, not as
// an own property of PosOrder.prototype, so
// `Object.getOwnPropertyDescriptor(PosOrder.prototype, "prices")` (which does
// NOT walk the prototype chain) returns undefined here unless some other
// module has already patched `prices` onto PosOrder.prototype as an own
// property first. Use a normal patch() with `super.prices` instead: `super`
// correctly walks the prototype chain regardless of patch order, so this
// composes correctly whether l10n_ve_loyalty_pos's own `prices` patch (the
// manual global discount) is installed and loaded before or after this one.
function l10nVePosCurrencyIdsSet(order) {
    const jsonIds = order.company?.l10n_ve_igtf_currency_pos_ids_json;
    if (jsonIds) {
        try {
            const ids = JSON.parse(jsonIds);
            if (Array.isArray(ids)) {
                return new Set(ids);
            }
        } catch {
            return new Set();
        }
    }
    const raw = order.company?.l10n_ve_igtf_currency_ids;
    const ids = Array.isArray(raw) ? raw : [];
    return new Set(
        ids.map((item) => {
            if (typeof item === "object" && item !== null) {
                return item.id ?? item;
            }
            return item;
        })
    );
}

function l10nVePosPaymentMethodAppliesIgtf(order, paymentMethod) {
    if (!order.company?.l10n_ve_igtf_feature_active) {
        return false;
    }
    const allowed = l10nVePosCurrencyIdsSet(order);
    if (!allowed.size) {
        return false;
    }
    const cur = paymentMethod?.payment_currency_id;
    const curId = typeof cur === "object" ? cur?.id : cur;
    return Boolean(curId && allowed.has(curId));
}

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        this.igtf_amount = vals.igtf_amount ?? 0;
        this.bi_igtf = vals.bi_igtf ?? 0;
    },

    l10n_ve_pos_updateIgtf() {
        const company = this.company;
        if (!company?.l10n_ve_igtf_feature_active || !this.isToInvoice()) {
            for (const pl of this.payment_ids) {
                pl.update({
                    include_igtf: false,
                    igtf_amount: 0,
                    foreign_igtf_amount: 0,
                });
            }
            this.update({ igtf_amount: 0, bi_igtf: 0 });
            return;
        }
        const percent = company.l10n_ve_igtf_percent ?? 0;
        let sumIgtf = 0;
        let sumBi = 0;

        // NOTE: `super.prices` here resolves to whatever patched `prices` was
        // installed on PosOrder.prototype *before* this module's own patch was
        // applied (e.g. l10n_ve_loyalty_pos's manual-global-discount total, if
        // that module's patch runs first). If l10n_ve_pos_igtf's patch instead
        // runs first, `super.prices` only sees Odoo's core total and this base
        // will not reflect an active manual discount. Both l10n_ve_loyalty_pos
        // and l10n_ve_pos_igtf only depend on point_of_sale (no dependency
        // between them), so their relative patch order is decided by the
        // asset bundle, not declared here.
        const baseTaxDetails = super.prices.taxDetails;
        const orderSign = baseTaxDetails.order_sign;
        const maxTotalWithTax = orderSign * baseTaxDetails.total_amount_no_rounding;
        const isReturn = maxTotalWithTax < 0;

        for (const pl of this.payment_ids) {
            pl.update({
                include_igtf: false,
                igtf_amount: 0,
                foreign_igtf_amount: 0,
            });
            if (!pl.payment_method_id || pl.is_change) {
                continue;
            }
            if (!l10nVePosPaymentMethodAppliesIgtf(this, pl.payment_method_id)) {
                continue;
            }
            let amountPay = pl.getAmount();
            const foreignPay =
                typeof pl.getPaymentAmountCurrency === "function"
                    ? pl.getPaymentAmountCurrency()
                    : amountPay;
            const payCur =
                typeof pl.getPaymentCurrency === "function"
                    ? pl.getPaymentCurrency()
                    : this.currency;
            const orderCur = this.currency;

            let isChangeLine = false;
            if (!isReturn) {
                isChangeLine = amountPay < 0;
            } else {
                isChangeLine = amountPay > 0;
            }
            if (isChangeLine) {
                continue;
            }

            if (
                (!isReturn && amountPay > maxTotalWithTax) ||
                (isReturn && amountPay < maxTotalWithTax)
            ) {
                amountPay = maxTotalWithTax;
            }

            const igtfLine = roundPrecision(amountPay * (percent / 100), this.currency.rounding);
            let igtfForeign = igtfLine;
            if (payCur && orderCur && payCur.id !== orderCur.id) {
                igtfForeign = roundPrecision(
                    foreignPay * (percent / 100),
                    payCur.decimal_places
                );
            }

            pl.update({
                include_igtf: true,
                igtf_amount: igtfLine,
                foreign_igtf_amount: igtfForeign,
            });
            sumIgtf += igtfLine;
            sumBi += amountPay;
        }
        this.update({
            igtf_amount: sumIgtf,
            bi_igtf: sumBi,
        });
    },

    // Odoo 19 dropped `taxTotals` and computes `remainingDue`/`change`/
    // `orderHasZeroRemaining` live from `totalDue` (itself derived from
    // `prices.taxDetails`) and `amountPaid`, instead of caching
    // order_remaining/order_rounding/order_has_zero_remaining inside
    // taxTotals the way Odoo 18 did. So the only thing that needs adjusting
    // here is the underlying total; the due/change/rounding getters then
    // pick up the IGTF surcharge automatically.
    get prices() {
        const base = super.prices;
        const igtfExtra = this.igtf_amount || 0;
        if (
            !this.company?.l10n_ve_igtf_feature_active ||
            !this.isToInvoice() ||
            floatIsZero(igtfExtra, this.currency.decimal_places)
        ) {
            return base;
        }
        const taxDetails = base.taxDetails;
        return {
            ...base,
            taxDetails: {
                ...taxDetails,
                total_amount_no_rounding: taxDetails.total_amount_no_rounding + igtfExtra,
                total_amount_currency: taxDetails.total_amount_currency + igtfExtra,
                total_amount: (taxDetails.total_amount ?? taxDetails.total_amount_currency) + igtfExtra,
            },
        };
    },

    addPaymentline(payment_method) {
        // Odoo 19 changed addPaymentline()'s return value from a plain
        // truthy/falsy result to a {status, data} object; `res` is now
        // always a (truthy) object even on failure, so this must check
        // `res.status` instead of `res` itself to keep only recomputing
        // IGTF after an actual successful add.
        const res = super.addPaymentline(...arguments);
        if (res?.status) {
            this.l10n_ve_pos_updateIgtf();
        }
        return res;
    },

    removePaymentline(line) {
        super.removePaymentline(...arguments);
        this.l10n_ve_pos_updateIgtf();
    },

    setToInvoice(to_invoice) {
        super.setToInvoice(...arguments);
        this.l10n_ve_pos_updateIgtf();
    },
});
