/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { MeaKpiCard } from "./mea_kpi_card";
import { MeaFtChart } from "./mea_ft_chart";
import { MeaUsageChart } from "./mea_usage_chart";

export class MeaDashboard extends Component {
    static template = "kob_mea_billing.MeaDashboard";
    static components = { MeaKpiCard, MeaFtChart, MeaUsageChart };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            metric: "amount",
            loading: true,
            range: 12,  // months back: 3 / 6 / 12 / 24 / 0=all
            sidebarExpanded: true,
            siteFilter: "",       // empty = all sites
            stateFilter: "",      // empty = all states
            anomalyOnly: false,
            kpis: {
                total_amount: 0,
                total_kwh: 0,
                ft_current: 0,
                anomaly_count: 0,
                meter_count: 0,
            },
            ftPeriods: [],
            bills: [],
            allBills: [],         // unfiltered cache
            meters: [],
        });

        onWillStart(async () => {
            await this._fetchAll();
        });
    }

    setRange(months) {
        this.state.range = months;
        this._fetchAll();
    }

    async _fetchAll() {
        const today = new Date();
        const months = this.state.range || 999;
        const startMonth = new Date(today.getFullYear(), today.getMonth() - (months - 1), 1);
        const startStr = startMonth.toISOString().slice(0, 10);

        const [periods, bills, meters] = await Promise.all([
            this.orm.searchRead(
                "mea.ft.period",
                [],
                ["period_start", "period_end", "ft_rate", "change_satang"],
                { order: "period_start asc" }
            ),
            this.orm.searchRead(
                "mea.bill.history",
                [["billing_month", ">=", startStr]],
                ["billing_month", "site_short", "kwh_total", "total_amount",
                 "expected_amount", "variance_pct", "is_anomaly", "state", "meter_id"],
                { order: "billing_month desc, site_short" }
            ),
            this.orm.searchRead(
                "mea.meter",
                [["state", "=", "active"]],
                ["id", "site_short", "ca_number", "meter_id", "tariff_id",
                 "last_total_amount", "last_bill_date"],
                { order: "site_short" }
            ),
        ]);
        const meterCount = meters.length;

        // Compute MoM % per site: ascending then back to descending
        const groupedBySite = {};
        for (const b of bills) {
            (groupedBySite[b.site_short] = groupedBySite[b.site_short] || []).push(b);
        }
        for (const site in groupedBySite) {
            const arr = groupedBySite[site].sort((a, b) => a.billing_month.localeCompare(b.billing_month));
            for (let i = 0; i < arr.length; i++) {
                const prev = arr[i - 1];
                arr[i].mom_amount_pct = prev && prev.total_amount
                    ? ((arr[i].total_amount - prev.total_amount) / prev.total_amount) * 100
                    : null;
                arr[i].mom_kwh_pct = prev && prev.kwh_total
                    ? ((arr[i].kwh_total - prev.kwh_total) / prev.kwh_total) * 100
                    : null;
            }
        }

        // Latest month KPI
        const latestMonth = bills.length ? bills[0].billing_month : null;
        const latestBills = bills.filter((b) => b.billing_month === latestMonth);
        const totalAmt = latestBills.reduce((s, b) => s + (b.total_amount || 0), 0);
        const totalKwh = latestBills.reduce((s, b) => s + (b.kwh_total || 0), 0);
        const anomalies = bills.filter((b) => b.is_anomaly).length;

        const todayStr = today.toISOString().slice(0, 10);
        const ftCurrent = periods.find(
            (p) => p.period_start <= todayStr && p.period_end >= todayStr
        );

        this.state.kpis = {
            total_amount: totalAmt,
            total_kwh: totalKwh,
            ft_current: ftCurrent ? ftCurrent.ft_rate : 0,
            anomaly_count: anomalies,
            meter_count: meterCount,
        };
        this.state.ftPeriods = periods;
        this.state.allBills = bills;
        this.state.bills = this._applyFilters(bills);
        this.state.meters = meters;
        this.state.loading = false;
    }

    _applyFilters(bills) {
        let out = [...bills];
        if (this.state.siteFilter) {
            out = out.filter((b) => b.site_short === this.state.siteFilter);
        }
        if (this.state.stateFilter) {
            out = out.filter((b) => b.state === this.state.stateFilter);
        }
        if (this.state.anomalyOnly) {
            out = out.filter((b) => b.is_anomaly);
        }
        return out;
    }

    setSiteFilter(site) {
        this.state.siteFilter = site;
        this.state.bills = this._applyFilters(this.state.allBills);
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

    openMeterDashboard(meterId) {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "kob_mea_meter_dashboard",
            name: "Meter Dashboard",
            context: { default_meter_id: meterId, active_id: meterId },
        });
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

    openHistoryList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mea.bill.history",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
        });
    }

    openCalculator() {
        this.action.doAction("kob_mea_billing.action_mea_calculator_wizard");
    }

    openImport() {
        this.action.doAction("kob_mea_billing.action_mea_pdf_import_wizard");
    }
}

registry.category("actions").add("kob_mea_dashboard", MeaDashboard);
