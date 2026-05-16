/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ThitiGanttView extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            rows: [],
            timelineStart: null,
            timelineEnd: null,
            loading: true,
        });
        onWillStart(this.loadData.bind(this));
    }

    async loadData() {
        const runId = this.props.action.context.default_run_id || null;
        const domain = runId ? [["run_id", "=", runId]] : [];
        const ops = await this.orm.searchRead(
            "thiti.plan.operation",
            domain,
            ["id", "reference", "operation_name", "item_id", "resource_id",
             "start_datetime", "end_datetime", "quantity", "status",
             "delay_days", "op_type"],
            { limit: 500, order: "start_datetime" },
        );
        if (!ops.length) {
            this.state.loading = false;
            return;
        }
        const start = Math.min(...ops.filter(o => o.start_datetime)
            .map(o => new Date(o.start_datetime).getTime()));
        const end = Math.max(...ops.filter(o => o.end_datetime)
            .map(o => new Date(o.end_datetime).getTime()));
        const span = end - start || 86400000;

        const byResource = {};
        for (const op of ops) {
            const resName = op.resource_id ? op.resource_id[1] : "Unassigned";
            if (!byResource[resName]) byResource[resName] = [];
            const s = op.start_datetime ? new Date(op.start_datetime).getTime() : start;
            const e = op.end_datetime ? new Date(op.end_datetime).getTime() : end;
            byResource[resName].push({
                id: op.id,
                label: op.operation_name || op.reference || "op",
                leftPct: ((s - start) / span) * 100,
                widthPct: Math.max(((e - s) / span) * 100, 0.5),
                late: (op.delay_days || 0) > 0,
                opType: op.op_type,
                qty: op.quantity,
            });
        }
        this.state.rows = Object.keys(byResource).sort().map(name => ({
            name, bars: byResource[name],
        }));
        this.state.timelineStart = new Date(start).toISOString().slice(0, 10);
        this.state.timelineEnd = new Date(end).toISOString().slice(0, 10);
        this.state.loading = false;
    }
}

ThitiGanttView.template = "kob_thiti_planning.GanttView";

registry.category("actions").add("thiti_gantt", ThitiGanttView);
