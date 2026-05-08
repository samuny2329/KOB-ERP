/** @odoo-module **/

import { Component, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { loadJS } from "@web/core/assets";

/**
 * Line chart of MEA Ft (Fuel Tariff) history.
 * Props:
 *   periods  array<{ period_start, period_end, ft_rate, change_satang }>
 */
export class MeaFtChart extends Component {
    static template = "kob_mea_billing.MeaFtChart";
    static props = {
        periods: Array,
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;

        onMounted(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            this.render_();
        });
        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    render_() {
        if (!this.canvasRef.el || !window.Chart) return;
        const data = [...this.props.periods].sort(
            (a, b) => new Date(a.period_start) - new Date(b.period_start)
        );
        const labels = data.map((p) => this._fmtPeriod(p.period_start, p.period_end));
        const values = data.map((p) => p.ft_rate);

        if (this.chart) {
            this.chart.destroy();
        }
        const ctx = this.canvasRef.el.getContext("2d");
        this.chart = new window.Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Ft (stang/kWh)",
                    data: values,
                    borderColor: "#7C3AED",
                    backgroundColor: "rgba(124, 58, 237, 0.12)",
                    borderWidth: 2.5,
                    pointRadius: 5,
                    pointBackgroundColor: "#7C3AED",
                    fill: true,
                    tension: 0.3,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `Ft: ${ctx.parsed.y.toFixed(2)} stang/kWh`,
                        },
                    },
                },
                scales: {
                    y: {
                        title: { display: true, text: "stang / kWh" },
                        beginAtZero: false,
                    },
                    x: {
                        title: { display: true, text: "Quarter" },
                    },
                },
            },
        });
    }

    _fmtPeriod(start, end) {
        const s = new Date(start);
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        return `${months[s.getMonth()]} ${s.getFullYear()}`;
    }
}
