import { _t } from "@web/core/l10n/translation";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

/** Accepted / total deal lines, clicked to expand the list (#52). */
export class DealLineCounter extends Component {
    static template = "crm_deals.DealLineCounter";
    static props = {
        ...standardWidgetProps,
    };

    onClick() {
        this.props.record.toggleDealLinesList();
    }

    get acceptedCount() {
        return this.props.record.data.deal_line_accepted_count;
    }

    get totalCount() {
        return this.props.record.data.deal_line_count;
    }

    get counterTitle() {
        return _t("%(acceptedCount)s deal lines accepted out of %(totalCount)s", {
            acceptedCount: this.acceptedCount,
            totalCount: this.totalCount,
        });
    }

    get counterDisplay() {
        return _t("%(count1)s/%(count2)s", {
            count1: this.acceptedCount,
            count2: this.totalCount,
        });
    }
}

export const dealLineCounter = {
    component: DealLineCounter,
    fieldDependencies: [
        { name: "deal_line_accepted_count", type: "integer" },
        { name: "deal_line_count", type: "integer" },
    ],
};

registry.category("view_widgets").add("deal_line_counter", dealLineCounter);
