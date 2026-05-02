/** @odoo-module **/

/**
 * KOB Account Report — minimal Enterprise-style report renderer.
 *
 * Reads `report_type` from action context (e.g. "profit_loss",
 * "balance_sheet", "journal_audit", "trial_balance") and calls the
 * matching backend method on `kob.account.report`. Renders a clean
 * table with toolbar (year, posted toggle, exports).
 */

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class KobAccountReport extends Component {
    static template = "kob_account_reports.AccountReport";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const ctx = (this.props.action && this.props.action.context) || {};
        const reportType = ctx.report_type || "profit_loss";
        this.config = REPORTS[reportType] || REPORTS.profit_loss;

        this.state = useState({
            year: new Date().getFullYear(),
            postedOnly: true,
            data: null,
            loading: true,
            expanded: {},
        });

        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(
                "kob.account.report",
                this.config.method,
                [],
                { year: this.state.year, posted_only: this.state.postedOnly },
            );
        } catch (e) {
            this.notification.add(_t("Failed to load report"), {
                type: "danger",
            });
            console.error(e);
        }
        this.state.loading = false;
    }

    onYearChange(delta) {
        this.state.year += delta;
        this.load();
    }
    togglePosted() {
        this.state.postedOnly = !this.state.postedOnly;
        this.load();
    }
    toggleRow(idx) {
        this.state.expanded[idx] = !this.state.expanded[idx];
    }

    fmt(n) {
        if (n === null || n === undefined) return "";
        return new Intl.NumberFormat("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(n);
    }

    get title() {
        return (this.state.data && this.state.data.title) || this.config.title;
    }
    get currency() {
        return (this.state.data && this.state.data.currency) || "฿";
    }
    get columns() {
        return (this.state.data && this.state.data.columns) || [];
    }
    get rows() {
        return (this.state.data && this.state.data.rows) || [];
    }
    get taxSummary() {
        return this.state.data && this.state.data.tax_summary;
    }
}

const REPORTS = {
    profit_loss: {
        title: "Profit and Loss",
        method: "get_profit_loss",
    },
    balance_sheet: {
        title: "Balance Sheet",
        method: "get_balance_sheet",
    },
    journal_audit: {
        title: "Journal Audit",
        method: "get_journal_audit",
    },
    trial_balance: {
        title: "Trial Balance",
        method: "get_trial_balance",
    },
};

registry.category("actions").add("kob_account_report", KobAccountReport);
