import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";

const TAX_LETTER_BY_RATE = [
    [0, "E"],
    [8, "R"],
    [16, "G"],
    [31, "S"],
];

function isVenezuelaCompany(order) {
    return (
        order?.company?.country_id?.code === "VE" ||
        order?.company?.account_fiscal_country_id?.code === "VE"
    );
}

function rateMatches(amount, target) {
    return Math.abs(Math.abs(amount) - target) < 0.01;
}

function getTaxLetterFromAmount(amount) {
    for (const [rate, letter] of TAX_LETTER_BY_RATE) {
        if (rateMatches(amount, rate)) {
            return letter;
        }
    }
    return null;
}

function stripTaxLetter(name) {
    return (name || "").replace(/\s*\([EGRS]\)\s*$/, "").trimEnd();
}

function appendTaxLetter(name, letter) {
    if (!letter) {
        return name;
    }
    const base = stripTaxLetter(name);
    if (!base) {
        return `(${letter})`;
    }
    return `${base} (${letter})`;
}

function isVenezuelaPriceOnlyProduct(line) {
    return Boolean(line?.product_id?.l10n_ve_pos_allow_price_change);
}

patch(PosOrderline.prototype, {
    // Odoo 19 renamed `set_quantity`/`get_quantity`/`assert_editable` to
    // camelCase on PosOrderline/PosOrder.
    setQuantity(quantity, keep_price) {
        if (
            isVenezuelaCompany(this.order_id) &&
            isVenezuelaPriceOnlyProduct(this) &&
            !this.refunded_orderline_id
        ) {
            const quant =
                typeof quantity === "number"
                    ? quantity
                    : parseFloat("" + (quantity ? quantity : 0));
            if (!Number.isNaN(quant) && Math.abs(quant) > 1) {
                quantity = Math.sign(quant) || 1;
            }
        }
        return super.setQuantity(quantity, keep_price);
    },
    merge(orderline) {
        if (
            isVenezuelaCompany(this.order_id) &&
            isVenezuelaPriceOnlyProduct(this)
        ) {
            this.order_id.assertEditable();
            if (Math.abs(this.getQuantity()) !== 1) {
                this.setQuantity(Math.sign(this.getQuantity()) || 1, true);
            }
            return;
        }
        return super.merge(...arguments);
    },
    _l10nVeGetLineTaxes() {
        const taxes = this.tax_ids?.length ? this.tax_ids : this.product_id?.taxes_id;
        if (!taxes?.length) {
            return [];
        }
        // Odoo 19 moved `getTaxesAfterFiscalPosition` from a standalone util
        // to a method on the fiscal position record itself.
        const fiscalPosition = this.order_id?.fiscal_position_id;
        return (fiscalPosition ? fiscalPosition.getTaxesAfterFiscalPosition(taxes) : taxes) || [];
    },
    _l10nVeGetTaxLetter() {
        if (!isVenezuelaCompany(this.order_id)) {
            return null;
        }
        const taxes = this._l10nVeGetLineTaxes().filter(
            (tax) => tax.amount_type === "percent"
        );
        if (!taxes.length) {
            return "E";
        }
        if (taxes.every((tax) => rateMatches(tax.amount, 0))) {
            return "E";
        }
        const taxed = taxes.find((tax) => !rateMatches(tax.amount, 0));
        return taxed ? getTaxLetterFromAmount(taxed.amount) : "E";
    },
    // Odoo 19 replaced `set_full_product_name`/`get_full_product_name` with
    // `setFullProductName`/`getFullProductName`.
    setFullProductName() {
        super.setFullProductName(...arguments);
        this.full_product_name = appendTaxLetter(
            this.full_product_name,
            this._l10nVeGetTaxLetter()
        );
    },
    getFullProductName() {
        return appendTaxLetter(
            super.getFullProductName(...arguments),
            this._l10nVeGetTaxLetter()
        );
    },
});
