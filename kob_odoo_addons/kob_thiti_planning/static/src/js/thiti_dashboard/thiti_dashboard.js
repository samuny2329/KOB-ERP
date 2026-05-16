/** @odoo-module **/

import { Component, onWillStart, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ThitiDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartRef = useRef("loadChart");
        this.state = useState({
            kpi: null,
            recentRuns: [],
            problems: { critical: 0, error: 0, warning: 0 },
            loading: true,
        });

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            this.renderChart();
        });
    }

    async loadData() {
        const runs = await this.orm.searchRead(
            "thiti.plan.run",
            [["state", "=", "done"]],
            ["id", "name", "duration_seconds", "item_count", "demand_count", "create_date"],
            { limit: 10, order: "create_date desc" },
        );
        this.state.recentRuns = runs;

        if (runs.length > 0) {
            const kpis = await this.orm.searchRead(
                "thiti.kpi",
                [["run_id", "=", runs[0].id]],
                ["service_level_pct", "capacity_utilization_pct", "average_delay_days",
                 "po_count", "mo_count", "do_count", "buffer_shortage_count",
                 "resource_overload_count", "plan_cost", "total_demands", "total_operations",
                 "problem_critical", "problem_error", "problem_warning"],
            );
            if (kpis.length > 0) this.state.kpi = kpis[0];
        }
        this.state.loading = false;
    }

    renderChart() {
        if (!this.chartRef.el || !this.state.kpi) return;
        if (typeof window.Chart === "undefined") return;
        const ctx = this.chartRef.el.getContext("2d");
        new window.Chart(ctx, {
            type: "doughnut",
            data: {
                labels: ["Service level", "Late"],
                datasets: [{
                    data: [
                        this.state.kpi.service_level_pct || 0,
                        100 - (this.state.kpi.service_level_pct || 0),
                    ],
                    backgroundColor: ["#2ECC71", "#C8102E"],
                }],
            },
            options: { responsive: true, maintainAspectRatio: false },
        });
    }

    openRun(runId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "thiti.plan.run",
            res_id: runId,
            views: [[false, "form"]],
        });
    }

    async createNewRun() {
        const action = await this.orm.call(
            "thiti.plan.run", "create",
            [[{ name: "New plan / " + new Date().toISOString().slice(0, 16), plan_horizon_days: 90 }]],
        );
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "thiti.plan.run",
            res_id: action[0],
            views: [[false, "form"]],
        });
    }
}

ThitiDashboard.template = "kob_thiti_planning.Dashboard";

registry.category("actions").add("thiti_dashboard", ThitiDashboard);
