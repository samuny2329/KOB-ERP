/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

/**
 * WmsPickDemandListController — row click on Daily Pick Demand opens the
 * WMS orders that contain that SKU on that order_date, by calling the
 * server-side `action_view_orders` method on the clicked record.
 * The underlying model is a SQL view with no form, so the default Odoo
 * openRecord (which expects a form view) is a no-op — we replace it.
 */
class WmsPickDemandListController extends ListController {
    setup() {
        super.setup();
        this._wmsAction = useService("action");
        this._wmsOrm    = useService("orm");
    }

    async openRecord(record) {
        const result = await this._wmsOrm.call(
            "wms.daily.pick.demand",
            "action_view_orders",
            [[record.resId]],
        );
        if (result) {
            await this._wmsAction.doAction(result);
        }
    }
}

registry.category("views").add("wms_pick_demand_list", {
    ...listView,
    Controller: WmsPickDemandListController,
});
