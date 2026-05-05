/** @odoo-module **/
/**
 * KOB ERP — "Customize" navbar button (Debug Mode only).
 *
 * One-click access to:
 *   - Edit the current action (ir.actions.act_window form)
 *   - Edit the current view (ir.ui.view form)
 *   - Edit the search view
 *   - Manage filters
 *
 * Visible only when Odoo is running in developer mode (?debug=1).
 * Hidden in normal user mode so end-users never see it.
 */

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class KobCustomizeButton extends Component {
    static template = "kob_base.CustomizeButton";
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
    }

    /**
     * Developer mode is on when env.debug is truthy.  We don't bother
     * with the assets vs. tests vs. normal flag distinction — any debug
     * level enables the button.
     */
    get isDebug() {
        return Boolean(this.env.debug);
    }

    /** Resolve the current controller's underlying ir.actions.act_window
     *  record, the view record we're rendering, and the search view. */
    _currentRefs() {
        const ctrl = this.action.currentController;
        if (!ctrl) {
            return { actionId: null, viewId: null, searchViewId: null };
        }
        const a = ctrl.action || {};
        const v = ctrl.view || {};
        const props = ctrl.props || {};
        return {
            actionId:     a.id || null,
            viewId:       v.id || props.viewId || null,
            searchViewId: a.search_view_id
                ? (Array.isArray(a.search_view_id)
                    ? a.search_view_id[0] : a.search_view_id)
                : null,
            modelName:    a.res_model || props.resModel || null,
        };
    }

    _openForm(model, resId, name) {
        if (!resId) {
            this.notification.add(
                `${name}: nothing to edit on this page.`,
                { type: "warning" },
            );
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "new",
        });
    }

    onEditAction() {
        const { actionId } = this._currentRefs();
        this._openForm("ir.actions.act_window", actionId, "Edit Action");
    }

    onEditView() {
        const { viewId } = this._currentRefs();
        this._openForm("ir.ui.view", viewId, "Edit View");
    }

    onEditSearchView() {
        const { searchViewId } = this._currentRefs();
        this._openForm("ir.ui.view", searchViewId, "Edit Search View");
    }

    onManageFilters() {
        const { modelName } = this._currentRefs();
        if (!modelName) {
            this.notification.add(
                "Manage Filters: no model on this page.",
                { type: "warning" },
            );
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Manage Filters",
            res_model: "ir.filters",
            views: [[false, "list"], [false, "form"]],
            domain: [["model_id", "=", modelName]],
            target: "current",
        });
    }
}

registry
    .category("systray")
    .add("kob_base.customize_button", {
        Component: KobCustomizeButton,
    }, { sequence: 60 });
