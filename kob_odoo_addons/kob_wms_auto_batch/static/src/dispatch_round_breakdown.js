/** @odoo-module **/
/**
 * Wire up clicks on the per-platform pipeline table cells
 * (`<a class="kob-dr-cell-link">`) so each cell drills into a list
 * view of orders for that (round, platform, stage) tuple.
 *
 * The HTML lives in ``wms.dispatch.round.breakdown_html`` (computed
 * server-side and rendered by Odoo's html widget).  We listen at the
 * document level so newly-rendered tables are picked up automatically
 * as the user navigates between rounds.
 */

import { registry } from "@web/core/registry";

const kobDrCellClickService = {
    dependencies: ["action", "orm", "notification"],
    start(env, { action, orm, notification }) {
        document.addEventListener("click", async (ev) => {
            const a = ev.target.closest("a.kob-dr-cell-link");
            if (!a) return;
            ev.preventDefault();
            ev.stopPropagation();
            const roundId  = parseInt(a.dataset.roundId, 10);
            const platform = a.dataset.platform || null;
            const stage    = a.dataset.stage    || null;
            if (!roundId) return;
            try {
                const actionDef = await orm.call(
                    "wms.dispatch.round",
                    "action_view_breakdown_cell",
                    [[roundId], platform, stage],
                );
                await action.doAction(actionDef);
            } catch (err) {
                notification.add(
                    `Could not open drill-down: ${err.message || err}`,
                    { type: "danger" },
                );
            }
        });
    },
};

registry
    .category("services")
    .add("kob_dr_cell_click", kobDrCellClickService);
