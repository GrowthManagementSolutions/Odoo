import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

/**
 * Customer Budget Summary (#58): each Accept / Reject writes the deal line
 * straight away. The server returns the document card re-rendered, so the
 * badges, buttons, subtotals and totals all move together, plus the sidebar
 * figures, without reloading the page.
 */
publicWidget.registry.CrmDealsBudgetSummary = publicWidget.Widget.extend({
    selector: ".o_budget_summary",
    events: {
        "click .o_budget_decision": "_onDecisionClick",
    },

    async _onDecisionClick(ev) {
        const button = ev.currentTarget;
        const { lineId, decision } = { lineId: button.dataset.lineId, decision: button.dataset.decision };
        const leadId = this.el.dataset.leadId;
        const token = this.el.dataset.accessToken;
        const buttons = this.el.querySelectorAll(".o_budget_decision");
        buttons.forEach((el) => (el.disabled = true));
        try {
            const result = await rpc(`/my/budget/${leadId}/line/${lineId}/${decision}`, {
                access_token: token,
            });
            if (result.error) {
                this._showError(result.error);
                buttons.forEach((el) => (el.disabled = false));
                return;
            }
            this._replaceContent(result.content);
            this._applyValues(result.values);
            this._applySignState(result.all_decided);
        } catch {
            buttons.forEach((el) => (el.disabled = false));
        }
    },

    /** Swap the document card for the freshly rendered one. */
    _replaceContent(content) {
        const card = this.el.querySelector("#budget_card");
        if (!card || !content) {
            return;
        }
        const parsed = new DOMParser().parseFromString(content, "text/html");
        const fresh = parsed.querySelector("#budget_card");
        if (fresh) {
            card.replaceWith(fresh);
        }
    },

    /** Sidebar totals, which sit outside the card. */
    _applyValues(values) {
        for (const [field, value] of Object.entries(values || {})) {
            this.el
                .querySelectorAll(`[data-budget-field="${field}"]`)
                .forEach((el) => (el.textContent = value));
        }
    },

    _applySignState(allDecided) {
        const signButton = this.el.querySelector(".o_budget_sign");
        if (signButton) {
            signButton.classList.toggle("disabled", !allDecided);
            if (allDecided) {
                signButton.removeAttribute("disabled");
            } else {
                signButton.setAttribute("disabled", "disabled");
            }
        }
    },

    _showError(message) {
        const alert = document.createElement("div");
        alert.className = "alert alert-danger alert-dismissible";
        alert.setAttribute("role", "alert");
        alert.textContent = message;
        this.el.querySelector("#budget_content")?.prepend(alert);
        setTimeout(() => alert.remove(), 6000);
    },
});

export default publicWidget.registry.CrmDealsBudgetSummary;
