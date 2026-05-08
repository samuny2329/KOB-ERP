/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { MeaKpiCard } from "./mea_kpi_card";
import { MeaUsageChart } from "./mea_usage_chart";

/**
 * Per-meter dashboard — opened from meter form smart button or via
 * action context {default_meter_id: <id>}.
 *
 * Shows:
 *   - 5 KPI cards specific to one meter
 *   - 12-month usage chart (kWh / amount toggle)
 *   - On Peak / Off Peak split (TOU only)
 *   - Demand kW trend
 *   - Recent bills table for this meter
 */
export class MeaMeterDashboard extends Component {
    static template = "kob_mea_billing.MeaMeterDashboard";
    static components = { MeaKpiCard, MeaUsageChart };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            metric: "amount",
            loading: true,
            meter: null,
            bills: [],
            allBills: [],
            kpis: {},
            topExpensive: [],
            topKwh: [],
            meters: [],
            currentMeterId: null,
            stateFilter: "",
            anomalyOnly: false,
            sidebarExpanded: true,
        });

        onWillStart(async () => {
            const meterId = this.props.action.context.default_meter_id || this.props.action.context.active_id;
            await this._loadMeters();
            if (!meterId) {
                this.state.loading = false;
                return;
            }
            this.state.currentMeterId = meterId;
            await this._fetchAll(meterId);
        });
    }

    async _loadMeters() {
        this.state.meters = await this.orm.searchRead(
            "mea.meter",
            [["state", "=", "active"]],
            ["id", "site_short"],
            { order: "site_short" }
        );
    }

    openMeterDashboard(meterId) {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "kob_mea_meter_dashboard",
            name: "Meter Dashboard",
            context: { default_meter_id: meterId, active_id: meterId },
        });
    }

    openCalculator() {
        this.action.doAction("kob_mea_billing.action_mea_calculator_wizard");
    }

    openImport() {
        this.action.doAction("kob_mea_billing.action_mea_pdf_import_wizard");
    }

    openHistoryList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mea.bill.history",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
        });
    }

    openMainDashboard() {
        this.action.doAction("kob_mea_billing.action_mea_dashboard");
    }

    _applyFilters(bills) {
        let out = [...bills];
        if (this.state.stateFilter) out = out.filter((b) => b.state === this.state.stateFilter);
        if (this.state.anomalyOnly) out = out.filter((b) => b.is_anomaly);
        return out;
    }

    setStateFilter(st) {
        this.state.stateFilter = st;
        this.state.bills = this._applyFilters(this.state.allBills);
    }

    toggleAnomaly() {
        this.state.anomalyOnly = !this.state.anomalyOnly;
        this.state.bills = this._applyFilters(this.state.allBills);
    }

    toggleSidebar() {
        this.state.sidebarExpanded = !this.state.sidebarExpanded;
    }

    async _fetchAll(meterId) {
        const [meter] = await this.orm.read("mea.meter", [meterId], [
            "site_short", "ca_number", "meter_id", "partner_name",
            "site_address", "district", "tariff_id", "is_tou", "state",
        ]);

        // Show all bill history for this meter (no date filter — multi-year ok)
        const raw = await this.orm.searchRead(
            "mea.bill.history",
            [["meter_id", "=", meterId]],
            ["billing_month", "site_short", "kwh_total", "kwh_on_peak", "kwh_off_peak",
             "demand_on_peak", "total_amount", "expected_amount", "variance_pct",
             "is_anomaly", "ft_rate", "state"],
            { order: "billing_month desc" }
        );

        // Sort ascending then compute Month-over-Month % delta vs previous row
        const sorted = [...raw].sort((a, b) => a.billing_month.localeCompare(b.billing_month));
        for (let i = 0; i < sorted.length; i++) {
            const prev = sorted[i - 1];
            sorted[i].mom_amount_pct = prev && prev.total_amount
                ? ((sorted[i].total_amount - prev.total_amount) / prev.total_amount) * 100
                : null;
            sorted[i].mom_kwh_pct = prev && prev.kwh_total
                ? ((sorted[i].kwh_total - prev.kwh_total) / prev.kwh_total) * 100
                : null;
        }
        const bills = sorted.reverse();  // newest first for table

        const last = bills[0] || {};
        const totalKwh12 = bills.reduce((s, b) => s + (b.kwh_total || 0), 0);
        const totalAmt12 = bills.reduce((s, b) => s + (b.total_amount || 0), 0);
        const anomalyCount = bills.filter((b) => b.is_anomaly).length;
        const peakDemand = Math.max(0, ...bills.map((b) => b.demand_on_peak || 0));

        // Top 5 most expensive + top 5 highest kWh
        const topExpensive = [...bills].sort((a, b) => b.total_amount - a.total_amount).slice(0, 5);
        const topKwh = [...bills].sort((a, b) => b.kwh_total - a.kwh_total).slice(0, 5);
        this.state.topExpensive = topExpensive;
        this.state.topKwh = topKwh;

        this.state.meter = meter;
        this.state.allBills = bills;
        this.state.bills = this._applyFilters(bills);
        this.state.kpis = {
            last_month_amount: last.total_amount || 0,
            last_month_kwh: last.kwh_total || 0,
            avg_amount_12mo: bills.length ? totalAmt12 / bills.length : 0,
            total_kwh_12mo: totalKwh12,
            anomaly_count: anomalyCount,
            peak_demand: peakDemand,
            last_ft_rate: last.ft_rate || 0,
        };
        this.state.loading = false;
    }

    formatTHB(v) {
        return (v || 0).toLocaleString("en-US", { maximumFractionDigits: 2 });
    }

    formatKwh(v) {
        return (v || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
    }

    toggleMetric() {
        this.state.metric = this.state.metric === "amount" ? "kwh" : "amount";
    }

    openBill(billId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mea.bill.history",
            res_id: billId,
            view_mode: "form",
            views: [[false, "form"]],
        });
    }

    backToMeters() {
        this.action.doAction("kob_mea_billing.action_mea_meter");
    }
}

registry.category("actions").add("kob_mea_meter_dashboard", MeaMeterDashboard);
