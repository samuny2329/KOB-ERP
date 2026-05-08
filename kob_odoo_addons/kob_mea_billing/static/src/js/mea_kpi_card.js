/** @odoo-module **/

import { Component } from "@odoo/owl";

/**
 * KPI card — displays a single metric with optional trend pct.
 * Props:
 *   title    string
 *   value    string (already formatted)
 *   unit     string ("THB" / "kWh" / "stang/kWh" / etc.)
 *   trend    number | null  (pct change vs prev period)
 *   color    "purple" | "teal" | "amber" | "rose" (theme accent)
 *   icon     string (Bootstrap icon class, e.g. "fa-bolt")
 */
export class MeaKpiCard extends Component {
    static template = "kob_mea_billing.MeaKpiCard";
    static props = {
        title: String,
        value: { type: [String, Number], optional: false },
        unit: { type: String, optional: true },
        trend: { type: [Number, { value: null }], optional: true },
        color: { type: String, optional: true },
        icon: { type: String, optional: true },
    };

    get trendClass() {
        if (this.props.trend == null) return "";
        return this.props.trend >= 0 ? "text-danger" : "text-success";
    }

    get trendArrow() {
        if (this.props.trend == null) return "";
        return this.props.trend >= 0 ? "↑" : "↓";
    }

    get trendDisplay() {
        if (this.props.trend == null) return "";
        return `${this.trendArrow} ${Math.abs(this.props.trend).toFixed(1)}%`;
    }
}
