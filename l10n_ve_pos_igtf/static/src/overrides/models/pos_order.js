import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { floatIsZero, roundPrecision } from "@web/core/utils/numbers";

const posOrderTaxTotalsDescriptor = Object.getOwnPropertyDescriptor(PosOrder.prototype, "taxTotals");
const rawTaxTotalsGetter = posOrderTaxTotalsDescriptor.get;

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
        if (!company?.l10n_ve_igtf_feature_active || !this.is_to_invoice()) {
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

        const baseTotals = rawTaxTotalsGetter.call(this);
        const orderSign = baseTotals.order_sign;
        const maxTotalWithTax = orderSign * baseTotals.order_total;
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
            let amountPay = pl.get_amount();
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

    get taxTotals() {
        const base = rawTaxTotalsGetter.call(this);
        const igtfExtra = this.igtf_amount || 0;
        if (
            !this.company?.l10n_ve_igtf_feature_active ||
            !this.is_to_invoice() ||
            floatIsZero(igtfExtra, this.currency.decimal_places)
        ) {
            return base;
        }
        const adjustedOrderTotal = base.order_total + igtfExtra;
        let remaining = adjustedOrderTotal;
        const documentSign = base.order_sign;
        const validPayments = this.payment_ids.filter((p) => p.is_done() && !p.is_change);
        let order_rounding = 0;
        for (const [payment, isLast] of validPayments.map((p, i) => [
            p,
            i === validPayments.length - 1,
        ])) {
            const paymentAmount = documentSign * payment.get_amount();
            if (isLast) {
                if (this.config.cash_rounding) {
                    const roundedRemaining = this.getRoundedRemaining(
                        this.config.rounding_method,
                        remaining
                    );
                    if (!floatIsZero(paymentAmount - remaining, this.currency.decimal_places)) {
                        order_rounding = roundedRemaining - remaining;
                    }
                }
            }
            remaining -= paymentAmount;
        }
        const remaining_with_rounding = remaining + order_rounding;
        return {
            ...base,
            order_total: adjustedOrderTotal,
            order_remaining: remaining,
            order_rounding,
            order_has_zero_remaining: floatIsZero(
                remaining_with_rounding,
                this.currency.decimal_places
            ),
        };
    },

    add_paymentline(payment_method) {
        const res = super.add_paymentline(...arguments);
        if (res) {
            this.l10n_ve_pos_updateIgtf();
        }
        return res;
    },

    remove_paymentline(line) {
        super.remove_paymentline(...arguments);
        this.l10n_ve_pos_updateIgtf();
    },

    set_to_invoice(to_invoice) {
        super.set_to_invoice(...arguments);
        this.l10n_ve_pos_updateIgtf();
    },
});
