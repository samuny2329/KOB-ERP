/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

const PALETTE = [
    "#7C3AED", "#0EA5E9", "#F59E0B", "#EF4444",
    "#10B981", "#EC4899", "#6366F1", "#84CC16",
];

/**
 * Bar chart of monthly kWh per site (12 months back).
 * Props:
 *   bills  array<{ billing_month, site_short, kwh_total, total_amount }>
 *   metric "kwh" | "amount"
 */
export class MeaUsageChart extends Component {
    static template = "kob_mea_billing.MeaUsageChart";
    static props = {
        bills: Array,
        metric: { type: String, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;

        onMounted(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            this._render();
        });
        onWillUpdateProps(() => this._render());
        onWillUnmount(() => {
            if (this.chart) this.chart.destroy();
        });
    }

    _render() {
        if (!this.canvasRef.el || !window.Chart) return;

        const metric = this.props.metric || "kwh";
        // group by site, sort by month
        const sites = new Map();
        const months = new Set();
        for (const b of this.props.bills) {
            const m = b.billing_month;
            months.add(m);
            if (!sites.has(b.site_short)) {
                sites.set(b.site_short, new Map());
            }
            sites.get(b.site_short).set(
                m,
                metric === "amount" ? b.total_amount : b.kwh_total
            );
        }
        const sortedMonths = [...months].sort();
        const labels = sortedMonths.map((m) => m.slice(0, 7));
        const datasets = [...sites.entries()].map(([name, data], i) => ({
            label: name,
            data: sortedMonths.map((m) => data.get(m) || 0),
            backgroundColor: PALETTE[i % PALETTE.length],
            borderRadius: 6,
        }));

        if (this.chart) this.chart.destroy();
        const ctx = this.canvasRef.el.getContext("2d");
        this.chart = new window.Chart(ctx, {
            type: "bar",
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "bottom" },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const v = ctx.parsed.y;
                                const unit = metric === "amount" ? " THB" : " kWh";
                                return `${ctx.dataset.label}: ${v.toLocaleString()}${unit}`;
                            },
                        },
                    },
                },
                scales: {
                    x: { stacked: false, grid: { display: false } },
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: metric === "amount" ? "THB" : "kWh",
                        },
                    },
                },
            },
        });
    }
}
