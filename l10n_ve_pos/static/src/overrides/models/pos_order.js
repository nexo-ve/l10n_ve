import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

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
    _l10nVePosOriginInvoiceJournal() {
        const originOrder = this.lines.find((line) => line.refunded_orderline_id)
            ?.refunded_orderline_id?.order_id;
        return originOrder?.invoice_journal_id || false;
    },
    canChangeInvoiceJournal() {
        return !(isVenezuelaCompany(this) && this.isRefund);
    },
    setInvoiceJournal(journal) {
        if (isVenezuelaCompany(this) && this.isRefund) {
            const originJournal = this._l10nVePosOriginInvoiceJournal();
            if (originJournal) {
                if (journal && journal.id !== originJournal.id) {
                    return;
                }
                journal = originJournal;
            }
        }
        this.update({
            invoice_journal_id: journal || false,
        });
        if (typeof this.l10n_ve_pos_updateIgtf === "function") {
            this.l10n_ve_pos_updateIgtf();
        }
    },
    // Odoo 19 renamed `set_to_invoice` to `setToInvoice` on PosOrder.
    setToInvoice(to_invoice) {
        if (isVenezuelaCompany(this) && !to_invoice) {
            return;
        }
        super.setToInvoice(...arguments);
    },
    // `getEmailItems` was removed from Odoo 19's PosOrder (it had no callers
    // left in core either); there is no longer a hook to patch, so this
    // override is dropped instead of patching a non-existent base method.
});
