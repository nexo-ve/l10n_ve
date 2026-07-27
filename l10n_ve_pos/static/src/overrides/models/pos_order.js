import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

function isVenezuelaCompany(order) {
    return (
        order.company?.country_id?.code === "VE" ||
        order.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(PosOrder.prototype, {
    setup(vals) {
        super.setup(vals);
        if (isVenezuelaCompany(this)) {
            this.to_invoice = true;
        }
    },
    setInvoiceJournal(journal) {
        this.update({
            invoice_journal_id: journal || false,
        });
        if (typeof this.l10n_ve_pos_updateIgtf === "function") {
            this.l10n_ve_pos_updateIgtf();
        }
    },
    set_to_invoice(to_invoice) {
        if (isVenezuelaCompany(this) && !to_invoice) {
            return;
        }
        super.set_to_invoice(...arguments);
    },
    getEmailItems() {
        if (isVenezuelaCompany(this)) {
            return [_t("the invoice")];
        }
        return super.getEmailItems(...arguments);
    },
});
