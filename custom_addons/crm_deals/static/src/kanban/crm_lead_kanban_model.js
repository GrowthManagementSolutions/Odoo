import { CrmKanbanModel } from "@crm/views/crm_kanban/crm_kanban_model";

/**
 * Deal-line list state on the pipeline kanban record (#52).
 *
 * Modelled on project's ProjectTaskRecord.toggleSubtasksList, but it cannot
 * reuse it: project's version builds the related activeFields out of
 * `this.config.fields`, which only works because a sub-task is the *same*
 * model as its parent. Deal lines are a different model, so the lines are
 * fetched straight through the ORM instead and kept on the record as plain
 * objects. Same outcome - nothing is read until the list is expanded, so the
 * pipeline does not fetch deal lines for every card up front.
 *
 * Both the counter widget and the list widget read this state, which is why it
 * lives on the record rather than inside either component. Records are
 * reactive, so assigning these properties re-renders the card; they are
 * initialised in setup() so the first read is tracked.
 */
export class CrmLeadKanbanRecord extends CrmKanbanModel.Record {
    setup() {
        super.setup(...arguments);
        this.displayDealLines = false;
        this.dealLines = [];
    }

    async toggleDealLinesList() {
        if (this.displayDealLines) {
            this.displayDealLines = false;
            return;
        }
        this.dealLines = await this.model.orm.searchRead(
            "crm.deal.line",
            [
                ["lead_id", "=", this.resId],
                ["display_type", "=", false],
            ],
            ["deal_ref", "product_id", "name", "status"],
            { order: "sequence, id" },
        );
        this.displayDealLines = true;
    }
}

CrmKanbanModel.Record = CrmLeadKanbanRecord;
