import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

/**
 * The deal lines expanded inside a pipeline card (#52), modelled on project's
 * SubtaskKanbanList. Read-only: no accept/reject and no inline editing, so
 * there is nothing like project's SubtaskCreate row here. Clicking a row opens
 * the deal form through the model's own action_open_deal_form, rather than
 * rebuilding that action in JS.
 */
export class DealLineKanbanList extends Component {
    static template = "crm_deals.DealLineKanbanList";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
    }

    get lines() {
        return this.props.record.dealLines || [];
    }

    /** Matches the Deals list decorations: accepted green, rejected red,
     *  draft grey. */
    statusClass(line) {
        return {
            accepted: "text-success",
            rejected: "text-danger",
        }[line.status] || "text-muted";
    }

    /** "<Deal ID> - <Product>", or just the product before an ID is stamped.
     *  A line that stopped at a layer has no product, so it falls back to its
     *  own label. */
    lineLabel(line) {
        const product = line.product_id ? line.product_id[1] : "";
        const label = product || line.name || "";
        return line.deal_ref ? `${line.deal_ref} - ${label}`.trim() : label;
    }

    async openDealLine(lineId) {
        const action = await this.orm.call(
            "crm.deal.line", "action_open_deal_form", [[lineId]]);
        return this.action.doAction(action);
    }
}

export const dealLineKanbanList = {
    component: DealLineKanbanList,
};

registry.category("view_widgets").add("deal_line_kanban_list", dealLineKanbanList);
