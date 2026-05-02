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
    // Statement
    profit_loss:           { title: "Profit and Loss",                method: "get_profit_loss" },
    balance_sheet:         { title: "Balance Sheet",                  method: "get_balance_sheet" },
    cash_flow:             { title: "Cash Flow Statement",            method: "get_cash_flow" },
    executive_summary:     { title: "Executive Summary",              method: "get_executive_summary" },
    tax_return:            { title: "Tax Return",                     method: "get_tax_return" },
    // Audit
    journal_audit:         { title: "Journal Audit",                  method: "get_journal_audit" },
    trial_balance:         { title: "Trial Balance",                  method: "get_trial_balance" },
    general_ledger:        { title: "General Ledger",                 method: "get_general_ledger" },
    // Partner
    partner_ledger:        { title: "Partner Ledger",                 method: "get_partner_ledger" },
    aged_receivable:       { title: "Aged Receivable",                method: "get_aged_receivable" },
    aged_payable:          { title: "Aged Payable",                   method: "get_aged_payable" },
    // Management
    invoice_analysis:      { title: "Invoice Analysis",               method: "get_invoice_analysis" },
    analytic_report:       { title: "Analytic Report",                method: "get_analytic_report" },
    unrealized_fx:         { title: "Unrealized Currency Gains/Losses", method: "get_unrealized_fx" },
    deferred_expense:      { title: "Deferred Expense",               method: "get_deferred_expense" },
    deferred_revenue:      { title: "Deferred Revenue",               method: "get_deferred_revenue" },
    depreciation_schedule: { title: "Depreciation Schedule",          method: "get_depreciation_schedule" },
    disallowed_expenses:   { title: "Disallowed Expenses",            method: "get_disallowed_expenses" },
    budget_report:         { title: "Budget Report",                  method: "get_budget_report" },
    loans_analysis:        { title: "Loans Analysis",                 method: "get_loans_analysis" },
};

registry.category("actions").add("kob_account_report", KobAccountReport);
