/** @odoo-module **/

/**
 * KOB ERP — Welcome dashboard.
 *
 * Client action rendered as the user's start screen after login.  Shows
 * every KOB ERP module + every standard Odoo app the company uses, each
 * with a short Thai/English description explaining what the module is for.
 * Clicking a card opens the corresponding Odoo action.
 */

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

class KobWelcome extends Component {
    static template = "kob_base.Welcome";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.menuService = useService("menu");
        this.notification = useService("notification");
        this.state = useState({ search: "", category: null });

        // Welcome is the start screen — clear any leftover currentApp /
        // currentMenu so the navbar doesn't keep showing submenus from the
        // module the user just came back from.
        onMounted(() => this._clearCurrentApp());
    }

    _clearCurrentApp() {
        try {
            // Odoo 19 menu service exposes setCurrentMenu(menu | undefined).
            if (this.menuService.setCurrentMenu) {
                this.menuService.setCurrentMenu(undefined);
            }
        } catch (_e) {
            /* best-effort; never block the welcome screen on this */
        }
    }

    /** Static catalogue — module key → metadata. */
    get modules() {
        return [
            // ── KOB ERP modules ────────────────────────────────────
            {
                key: "kob_erp",
                name: "KOB ERP",
                description: _t(
                    "Top-level KOB ERP menu — Thailand Compliance, Group, " +
                    "Marketplace, WH-Online E-Commerce, KPI & Dashboards.",
                ),
                category: "kob",
                color: "#0a6ed1",
                glyph: "K",
                menuXmlId: "kob_base.menu_kob_root",
            },
            {
                key: "kob_thai_compliance",
                name: _t("Thailand Compliance"),
                description: _t(
                    "SSO 5%+5% (capped 750฿), PND withholding tax brackets, " +
                    "Thai LPA overtime (1.5×/3×), annual leave, fixed-asset " +
                    "depreciation, FX revaluation.",
                ),
                category: "kob",
                color: "#107e3e",
                glyph: "ภ",
                menuXmlId: "kob_base.menu_kob_thai",
            },
            {
                key: "kob_group",
                name: _t("Group / Multi-company"),
                description: _t(
                    "Multi-company KPI snapshots, group treasury, " +
                    "intercompany transfers, consolidated reports.",
                ),
                category: "kob",
                color: "#5d9ff5",
                glyph: "Σ",
                menuXmlId: "kob_base.menu_kob_group",
            },
            {
                key: "kob_marketplace",
                name: _t("Marketplace"),
                description: _t(
                    "Shopee · Lazada · TikTok platform integration — " +
                    "unified order feed, channel margin, fee accounts.",
                ),
                category: "kob",
                color: "#e9730c",
                glyph: "M",
                menuXmlId: "kob_base.menu_kob_marketplace",
            },
            {
                key: "kob_wh_online",
                name: _t("WH-Online E-Commerce"),
                description: _t(
                    "Warehouse fulfilment for online orders — Pick · Pack · " +
                    "Outbound · Dispatch screens, scan-driven workflow.",
                ),
                category: "kob",
                color: "#354a5f",
                glyph: "W",
                // Direct to the kob_wms root menu installed by the WMS addon.
                menuXmlId: "kob_wms.menu_kob_wms_root",
            },
            {
                key: "kob_kpi",
                name: _t("KPI & Dashboards"),
                description: _t(
                    "Worker performance, OEE, quality scorecards, " +
                    "consolidated executive dashboards.",
                ),
                category: "kob",
                color: "#bb0000",
                glyph: "📊",
                menuXmlId: "kob_base.menu_kob_kpi",
            },
            // ── Standard Odoo apps the business uses ──────────────
            {
                key: "sales",
                name: _t("Sales"),
                description: _t(
                    "Quotations to invoices — customer pricelists, sales " +
                    "teams, lost reasons, won/lost analytics.",
                ),
                category: "operations",
                color: "#0a6ed1",
                glyph: "$",
                actionXmlId: "sale.action_quotations_with_onboarding",
            },
            {
                key: "purchase",
                name: _t("Purchase"),
                description: _t(
                    "Purchase orders, vendor pricelists, RFQ workflow, " +
                    "approval matrix, vendor performance.",
                ),
                category: "operations",
                color: "#107e3e",
                glyph: "₱",
                actionXmlId: "purchase.purchase_rfq",
            },
            {
                key: "inventory",
                name: _t("Inventory"),
                description: _t(
                    "Warehouses, stock moves, inventory adjustments, " +
                    "putaway rules, valuation, reorder points.",
                ),
                category: "operations",
                color: "#5d9ff5",
                glyph: "📦",
                menuXmlId: "stock.menu_stock_root",
            },
            {
                key: "mrp",
                name: _t("Manufacturing"),
                description: _t(
                    "MRP — manufacturing orders, BoMs, work orders, " +
                    "routings, work centres, OEE.",
                ),
                category: "operations",
                color: "#e9730c",
                glyph: "⚙",
                menuXmlId: "mrp.menu_mrp_root",
            },
            {
                key: "crm",
                name: _t("CRM"),
                description: _t(
                    "Lead → Opportunity → Quotation pipeline, sales " +
                    "activities, won-rate reporting.",
                ),
                category: "sales_marketing",
                color: "#bb0000",
                glyph: "♥",
                menuXmlId: "crm.crm_menu_root",
            },
            {
                key: "website",
                name: _t("Website"),
                description: _t(
                    "Corporate site, blog, e-commerce storefront — " +
                    "drag-and-drop CMS.",
                ),
                category: "sales_marketing",
                color: "#0a6ed1",
                glyph: "🌐",
                menuXmlId: "website.menu_website_configuration",
            },
            {
                key: "accounting",
                name: _t("Accounting"),
                description: _t(
                    "Journal entries, customer/vendor invoices, payments, " +
                    "bank reconciliation, financial reports.",
                ),
                category: "finance",
                color: "#354a5f",
                glyph: "₿",
                menuXmlId: "account.menu_finance",
            },
            {
                key: "hr",
                name: _t("Employees"),
                description: _t(
                    "Employee directory, departments, contracts, " +
                    "skills, onboarding.",
                ),
                category: "people",
                color: "#107e3e",
                glyph: "👤",
                menuXmlId: "hr.menu_hr_root",
            },
            {
                key: "calendar",
                name: _t("Calendar"),
                description: _t(
                    "Meetings, appointments, shared team calendars.",
                ),
                category: "productivity",
                color: "#e9730c",
                glyph: "📅",
                menuXmlId: "calendar.mail_menu_calendar",
            },
            {
                key: "discuss",
                name: _t("Discuss"),
                description: _t(
                    "Internal chat channels, mentions, file sharing.",
                ),
                category: "productivity",
                color: "#5d9ff5",
                glyph: "💬",
                menuXmlId: "mail.menu_root_discuss",
            },
            {
                key: "contacts",
                name: _t("Contacts"),
                description: _t(
                    "Customers, vendors, address book — shared partner " +
                    "directory used by every business module.",
                ),
                category: "sales_marketing",
                color: "#5d9ff5",
                glyph: "📇",
                menuXmlId: "contacts.menu_contacts",
            },
            {
                key: "pos",
                name: _t("Point of Sale"),
                description: _t(
                    "Retail POS — open shifts, scan barcodes, print receipts, " +
                    "sync to inventory and accounting in real time.",
                ),
                category: "operations",
                color: "#bb0000",
                glyph: "🛒",
                menuXmlId: "point_of_sale.menu_point_root",
            },
            {
                key: "dashboards",
                name: _t("Dashboards"),
                description: _t(
                    "Spreadsheet-style dashboards — pivot, charts, KPIs, " +
                    "with native Odoo data sources.",
                ),
                category: "productivity",
                color: "#107e3e",
                glyph: "📊",
                menuXmlId: "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
            },
            {
                key: "apps",
                name: _t("Apps"),
                description: _t(
                    "Module manager — browse, install, upgrade or remove " +
                    "Odoo + KOB addons for this database.",
                ),
                category: "admin",
                color: "#354a5f",
                glyph: "⊞",
                menuXmlId: "base.menu_management",
            },
            {
                key: "settings",
                name: _t("Settings"),
                description: _t(
                    "System configuration — companies, users, languages, " +
                    "permissions, multi-company group settings.",
                ),
                category: "admin",
                color: "#6a6d70",
                glyph: "⚙",
                menuXmlId: "base.menu_administration",
            },
        ];
    }

    get categories() {
        return [
            { id: "kob", label: _t("KOB ERP"), color: "#0a6ed1" },
            { id: "operations", label: _t("Operations"), color: "#107e3e" },
            { id: "sales_marketing", label: _t("Sales & Marketing"), color: "#bb0000" },
            { id: "finance", label: _t("Finance"), color: "#354a5f" },
            { id: "people", label: _t("People"), color: "#e9730c" },
            { id: "productivity", label: _t("Productivity"), color: "#5d9ff5" },
            { id: "admin", label: _t("Administration"), color: "#6a6d70" },
        ];
    }

    get filteredModules() {
        const q = this.state.search.trim().toLowerCase();
        return this.modules.filter((m) => {
            if (this.state.category && m.category !== this.state.category) return false;
            if (q && !`${m.name} ${m.description}`.toLowerCase().includes(q)) return false;
            return true;
        });
    }

    grouped() {
        const buckets = {};
        for (const m of this.filteredModules) {
            (buckets[m.category] ??= []).push(m);
        }
        return this.categories
            .map((c) => ({ ...c, modules: buckets[c.id] || [] }))
            .filter((c) => c.modules.length > 0);
    }

    /** Walk a menu and its descendants until we find one with an
     *  actionID; selectMenu on that one sets the navbar's currentApp
     *  correctly so submenus render. */
    _firstActionableDescendant(menu, all) {
        if (menu.actionID) return menu;
        const byId = new Map(all.map((m) => [m.id, m]));
        const stack = [...(menu.children || [])];
        while (stack.length) {
            const childId = stack.shift();
            const child = byId.get(childId);
            if (!child) continue;
            if (child.actionID) return child;
            stack.push(...(child.children || []));
        }
        return null;
    }

    async onCardClick(mod) {
        const all = this.menuService.getAll ? this.menuService.getAll() : [];

        // 1. Direct menu lookup by xmlid.
        if (mod.menuXmlId) {
            const menu = all.find((m) => m && m.xmlid === mod.menuXmlId);
            if (menu) {
                const actionable = this._firstActionableDescendant(menu, all);
                if (actionable && this.menuService.selectMenu) {
                    await this.menuService.selectMenu(actionable);
                    return;
                }
                if (menu.appID && this.menuService.selectMenu) {
                    // App-only menu with no children — open the app itself.
                    const app = all.find((m) => m.id === menu.appID);
                    if (app && app.actionID) {
                        await this.menuService.selectMenu(app);
                        return;
                    }
                }
                // Menu exists but has no actionable descendant (placeholder).
                this._notifyMissing(mod, _t(
                    "Menu has no actionable child. Install a sub-module " +
                    "or add a view under this menu first."
                ));
                return;
            }
        }

        // 2. Action xmlid → resolve to action_id → find owning menu.
        if (mod.actionXmlId) {
            try {
                const resolved = await this.action.loadAction(mod.actionXmlId);
                const actionId = resolved && resolved.id;
                if (actionId) {
                    const owner = all.find(
                        (m) => m && m.actionID === actionId,
                    );
                    if (owner && this.menuService.selectMenu) {
                        await this.menuService.selectMenu(owner);
                        return;
                    }
                }
                // Fallback: just open the action without setting currentApp.
                await this.action.doAction(mod.actionXmlId);
                return;
            } catch (e) {
                console.warn(
                    "[KobWelcome] action unavailable",
                    mod.actionXmlId,
                    e,
                );
                this._notifyMissing(mod, _t(
                    "Action not available. The module providing this " +
                    "feature may not be installed."
                ));
                return;
            }
        }

        // 3. Neither menu nor action could resolve.
        this._notifyMissing(mod, _t(
            "Module not installed. Open the Apps screen to install it."
        ));
    }

    _notifyMissing(mod, hint) {
        if (!this.notification) {
            return;
        }
        this.notification.add(hint, {
            title: mod.name,
            type: "warning",
            sticky: false,
        });
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
    }

    onCategoryClick(catId) {
        this.state.category = this.state.category === catId ? null : catId;
    }
}

registry.category("actions").add("kob_base.welcome", KobWelcome);
