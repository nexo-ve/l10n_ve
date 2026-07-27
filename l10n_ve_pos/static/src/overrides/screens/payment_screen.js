import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { onMounted, useState } from "@odoo/owl";

function isVenezuelaCompany(pos) {
    return (
        pos.company?.country_id?.code === "VE" ||
        pos.company?.account_fiscal_country_id?.code === "VE"
    );
}

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.l10nVeEmission = useState({
            emission_medium: this.pos.config.l10n_ve_invoice_journal_emission_medium || "",
            journal_display_name: this.pos.config.l10n_ve_invoice_journal_display_name || "",
            next_free_control_number: this.pos.config.l10n_ve_pos_next_free_control_number || "",
        });
        onMounted(() => this.l10nVeRefreshEmissionPreview());
    },
    get availableInvoiceJournals() {
        if (!isVenezuelaCompany(this.pos)) {
            return [];
        }
        return this.pos.getAvailableInvoiceJournals();
    },
    async clickInvoiceJournal() {
        const journal = await this.pos.selectInvoiceJournal(this.currentOrder);
        if (journal) {
            await this.l10nVeRefreshEmissionPreview();
        }
    },
    async l10nVeRefreshEmissionPreview() {
        if (!isVenezuelaCompany(this.pos)) {
            return;
        }
        const journalId = this.currentOrder?.invoice_journal_id?.id || false;
        const data = await this.pos.data.call(
            "pos.config",
            "l10n_ve_get_invoice_emission_preview",
            [[this.pos.config.id], journalId]
        );
        if (!data) {
            return;
        }
        this.l10nVeEmission.emission_medium = data.emission_medium || "";
        this.l10nVeEmission.journal_display_name = data.journal_display_name || "";
        this.l10nVeEmission.next_free_control_number = data.next_free_control_number || "";
        this.pos.config.l10n_ve_invoice_journal_emission_medium = data.emission_medium || false;
        this.pos.config.l10n_ve_invoice_journal_display_name = data.journal_display_name || false;
        this.pos.config.l10n_ve_pos_next_free_control_number =
            data.next_free_control_number || false;
        this.pos.config.l10n_ve_pos_free_book_section_name =
            data.free_book_section_name || false;
    },
    get isVenezuelaPos() {
        return isVenezuelaCompany(this.pos);
    },
    get l10nVeInvoiceJournalDisplayName() {
        const orderJournal = this.currentOrder?.invoice_journal_id;
        if (orderJournal) {
            return orderJournal.display_name || orderJournal.name || _t("Select journal");
        }
        return this.l10nVeEmission.journal_display_name || _t("Select journal");
    },
    async afterOrderValidation() {
        if (isVenezuelaCompany(this.pos)) {
            this.pos.showScreen("ReceiptScreen");
            if (!this.pos.config.module_pos_restaurant) {
                this.pos.checkPreparationStateAndSentOrderInPreparation(this.currentOrder);
            }
            return;
        }
        await super.afterOrderValidation(...arguments);
    },
    toggleIsToInvoice() {
        if (isVenezuelaCompany(this.pos)) {
            return;
        }
        super.toggleIsToInvoice(...arguments);
    },
    shouldDownloadInvoice() {
        if (isVenezuelaCompany(this.pos)) {
            return false;
        }
        return super.shouldDownloadInvoice(...arguments);
    },
    get l10nVeShowPaymentEmissionPanel() {
        if (!this.isVenezuelaPos || !this.currentOrder?.is_to_invoice?.()) {
            return false;
        }
        return ["free", "fiscal_machine", "digital"].includes(
            this.l10nVeJournalEmissionMedium
        );
    },
    get l10nVeJournalEmissionMedium() {
        const orderMedium = this.currentOrder?.invoice_journal_id?.l10n_ve_emission_medium;
        if (orderMedium) {
            return orderMedium;
        }
        return this.l10nVeEmission.emission_medium || "";
    },
    get l10nVeNextFreeControlNumber() {
        return this.l10nVeEmission.next_free_control_number || "";
    },
    get l10nVeLabelNextControl() {
        return _t("Next control number");
    },
    get l10nVeLabelFiscalInvoiceNo() {
        return _t("Fiscal invoice number");
    },
    get l10nVeLabelFiscalSerial() {
        return _t("Fiscal machine serial");
    },
    get l10nVeLabelFiscalZ() {
        return _t("Z report number");
    },
    get l10nVeLabelControlNumber() {
        return _t("Control number");
    },
    get l10nVeDash() {
        return "—";
    },
    get l10nVeNextFreeControlNumberDisplay() {
        return this.l10nVeNextFreeControlNumber || this.l10nVeDash;
    },
    get l10nVeLabelAmountWithoutTaxes() {
        return _t("Amount without taxes");
    },
    get l10nVeAmountWithoutTaxesDisplay() {
        if (!this.currentOrder) {
            return this.env.utils.formatCurrency(0);
        }
        return this.env.utils.formatCurrency(this.currentOrder.get_total_without_tax());
    },
});
