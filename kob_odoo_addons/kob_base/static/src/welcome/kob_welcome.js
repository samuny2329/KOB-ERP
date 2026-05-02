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
        this.state = useState({
            search: "",
            category: null,
            order: this._loadOrder(),
            draggingKey: null,
            dragOverKey: null,
        });

        // Welcome is the start screen — clear any leftover currentApp /
        // currentMenu so the navbar doesn't keep showing submenus from the
        // module the user just came back from.
        onMounted(() => this._clearCurrentApp());
    }

    // ── DRAG-AND-DROP REORDER ──────────────────────────────────────
    _orderKey() {
        return "kob_welcome_app_order_v1";
    }
    _loadOrder() {
        try {
            const raw = window.localStorage.getItem(this._orderKey());
            return raw ? JSON.parse(raw) : [];
        } catch (_e) {
            return [];
        }
    }
    _saveOrder(order) {
        try {
            window.localStorage.setItem(this._orderKey(), JSON.stringify(order));
        } catch (_e) {
            /* quota exceeded — ignore */
        }
    }

    /** Apply the saved order to a list of modules. Unknown keys keep
     *  their original relative order at the end. */
    _applyOrder(mods) {
        if (!this.state.order || !this.state.order.length) {
            return mods;
        }
        const indexOf = new Map(this.state.order.map((k, i) => [k, i]));
        return [...mods].sort((a, b) => {
            const ai = indexOf.has(a.key) ? indexOf.get(a.key) : 1e6;
            const bi = indexOf.has(b.key) ? indexOf.get(b.key) : 1e6;
            return ai - bi;
        });
    }

    onDragStart(ev, key) {
        this.state.draggingKey = key;
        try {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", key);
        } catch (_e) {/* */}
    }
    onDragOver(ev, key) {
        ev.preventDefault();
        try { ev.dataTransfer.dropEffect = "move"; } catch (_e) {/* */}
        if (this.state.dragOverKey !== key) {
            this.state.dragOverKey = key;
        }
    }
    onDragLeave(ev, key) {
        if (this.state.dragOverKey === key) {
            this.state.dragOverKey = null;
        }
    }
    onDrop(ev, dropKey) {
        ev.preventDefault();
        const dragKey = this.state.draggingKey;
        this.state.draggingKey = null;
        this.state.dragOverKey = null;
        if (!dragKey || dragKey === dropKey) {
            return;
        }
        // Build current effective order from filteredModules (matches what user sees).
        const visible = this.filteredModules.map((m) => m.key);
        const fromIdx = visible.indexOf(dragKey);
        const toIdx = visible.indexOf(dropKey);
        if (fromIdx < 0 || toIdx < 0) {
            return;
        }
        visible.splice(toIdx, 0, visible.splice(fromIdx, 1)[0]);

        // Merge the reordered visible keys back into the full order list.
        const allKeys = this.modules.map((m) => m.key);
        const fullOrder = this.state.order && this.state.order.length
            ? [...this.state.order]
            : [...allKeys];
        // Remove visible keys from fullOrder, then re-insert in new order at the
        // position of the first removed one.
        const visibleSet = new Set(visible);
        const firstPos = fullOrder.findIndex((k) => visibleSet.has(k));
        const cleaned = fullOrder.filter((k) => !visibleSet.has(k));
        const insertAt = firstPos < 0 ? cleaned.length : firstPos;
        cleaned.splice(insertAt, 0, ...visible);
        // Append any keys never seen.
        for (const k of allKeys) {
            if (!cleaned.includes(k)) cleaned.push(k);
        }
        this.state.order = cleaned;
        this._saveOrder(cleaned);
    }
    onDragEnd() {
        this.state.draggingKey = null;
        this.state.dragOverKey = null;
    }
    resetOrder() {
        this.state.order = [];
        this._saveOrder([]);
    }

    _clearCurrentApp() {
        // Odoo 19's menu service ignores `setCurrentMenu(undefined)` — so the
        // closure-private currentAppId stays pinned on whatever module the
        // user opened previously.  The actual hiding of the leftover submenu
        // is done by a NavBar getter override (see kob_brand.js); here we
        // just bus-trigger MENUS:APP-CHANGED so the navbar re-renders and
        // re-reads our overridden `currentApp` getter.
        try {
            this.env && this.env.bus && this.env.bus.trigger("MENUS:APP-CHANGED");
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
                key: "kob_kpi_live",
                name: _t("Live KPI Dashboard"),
                description: _t(
                    "Real-time KPI tiles: Sales 30d, AR/AP outstanding, " +
                    "inventory value, helpdesk load, top movers.",
                ),
                category: "kob",
                color: "#bb0000",
                glyph: "📊",
                menuXmlId: "kob_kpi_tiles.menu_kob_kpi_dashboard",
            },
            {
                key: "kob_tools",
                name: _t("KOB Tools"),
                description: _t(
                    "Onboarding wizard, bulk import, kiosk sessions, " +
                    "demand forecast, vendor scorecard, invoice OCR, " +
                    "approval workflow, ESG, AI suggestions, API console.",
                ),
                category: "kob",
                color: "#9f4ee0",
                glyph: "🧰",
                menuXmlId: "kob_extras_v4.menu_kob_extras_root",
            },
            {
                key: "kob_helpdesk",
                name: _t("Helpdesk"),
                description: _t(
                    "Ticket queue with categories, state machine, " +
                    "auto-sequence numbering, internal SLA.",
                ),
                category: "kob",
                color: "#0a6ed1",
                glyph: "🎫",
                menuXmlId: "kob_helpdesk.menu_kob_helpdesk_root",
            },
            {
                key: "kob_backup",
                name: _t("Backup &amp; DR"),
                description: _t(
                    "Scheduled DB backup with 14-day retention; " +
                    "log of every snapshot for audit & disaster recovery.",
                ),
                category: "kob",
                color: "#354a5f",
                glyph: "💾",
                menuXmlId: "kob_backup.menu_kob_backup_root",
            },
            {
                key: "kob_webhooks",
                name: _t("Webhooks"),
                description: _t(
                    "Outbound HTTP webhooks fired on configurable model " +
                    "events; delivery log with retry tracking.",
                ),
                category: "kob",
                color: "#107e3e",
                glyph: "🔗",
                menuXmlId: "kob_webhooks.menu_kob_webhooks_root",
            },
            // ── Phase-3/4/8 advanced + Phase-11/12/13 group ──────
            {
                key: "kob_purchase_pro",
                name: _t("Purchase Pro"),
                description: _t(
                    "Vendor performance scoring, procurement budget gating, " +
                    "demand signal, PO consolidation, vendor compliance docs.",
                ),
                category: "kob",
                color: "#107e3e",
                glyph: "₱",
                menuXmlId: "kob_purchase_pro.menu_kob_purchase_pro_root",
            },
            {
                key: "kob_sales_pro",
                name: _t("Sales Pro"),
                description: _t(
                    "RMA returns workflow, multi-platform order linkage, " +
                    "channel margin, customer LTV, intercompany SO mirror.",
                ),
                category: "kob",
                color: "#0a6ed1",
                glyph: "$",
                menuXmlId: "kob_sales_pro.menu_kob_sales_pro_root",
            },
            {
                key: "kob_mfg_pro",
                name: _t("Manufacturing Pro"),
                description: _t(
                    "Per-shift OEE, production shifts, MO production " +
                    "signals from sales velocity, batch consolidation.",
                ),
                category: "kob",
                color: "#e9730c",
                glyph: "⚙",
                menuXmlId: "kob_mfg_pro.menu_kob_mfg_pro_root",
            },
            {
                key: "kob_group",
                name: _t("Multi-Company Group"),
                description: _t(
                    "Inventory pools, approval matrix, cost allocation, " +
                    "intercompany loans, cash pool, transfer pricing, " +
                    "volume rebates, cross-co partners, brand licenses.",
                ),
                category: "kob",
                color: "#5d9ff5",
                glyph: "Σ",
                menuXmlId: "kob_group.menu_kob_group_root",
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
        const filtered = this.modules.filter((m) => {
            if (this.state.category && m.category !== this.state.category) return false;
            if (q && !`${m.name} ${m.description}`.toLowerCase().includes(q)) return false;
            return true;
        });
        return this._applyOrder(filtered);
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

    /** AI suggestion chip click — pre-fill the prompt and clear category. */
    applySuggest(query) {
        this.state.search = query;
        this.state.category = null;
    }
}

registry.category("actions").add("kob_base.welcome", KobWelcome);
