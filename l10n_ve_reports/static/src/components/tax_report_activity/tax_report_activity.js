/** @odoo-module */
import {patch} from "@web/core/utils/patch";
import {ActivityListPopoverItem} from "@mail/core/web/activity_list_popover_item";

patch(ActivityListPopoverItem.prototype, {
    get isTaxReportActivity() {
        return this.props.activity.activity_category === "tax_report";
    },

    async onClickOpenTaxActivity() {
        const action = await this.env.services.orm.call(
            "mail.activity",
            "action_open_tax_activity",
            [this.props.activity.id],
            {}
        );
        this.props.onActivityChanged?.();
        this.env.services.action.doAction(action);
    },
});
