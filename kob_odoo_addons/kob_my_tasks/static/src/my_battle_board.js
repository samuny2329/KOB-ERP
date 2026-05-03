/** @odoo-module **/

/**
 * 🔥 My Battle Board — Personal task inbox aggregating work across
 * all KOB modules, filtered by user role.
 */
import { Component, onMounted, onWillUnmount, useState }
    from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { standardActionServiceProps }
    from "@web/webclient/actions/action_service";

const REFRESH_INTERVAL_MS = 30_000;

class MyBattleBoard extends Component {
    static template = "kob_my_tasks.MyBattleBoard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            data: null,
            search: "",
            category: "all",
            lastUpdated: null,
            quickCreate: { name: "", priority: "1", due_date: "" },
            creating: false,
        });

        onMounted(async () => {
            await this.refresh();
            this._timer = setInterval(() => this.refresh(true),
                                      REFRESH_INTERVAL_MS);
        });
        onWillUnmount(() => {
            if (this._timer) clearInterval(this._timer);
        });
    }

    // ── Data ─────────────────────────────────────────────────────
    async refresh(silent = false) {
        if (!silent) this.state.loading = true;
        try {
            const data = await this.orm.call(
                "kob.my.task", "get_inbox", [], {});
            this.state.data = data;
            this.state.lastUpdated = new Date();
        } catch (e) {
            if (!silent) {
                this.notification.add(
                    _t("ไม่สามารถโหลด My Battle Board ได้"),
                    { type: "danger" });
            }
            console.error(e);
        } finally {
            if (!silent) this.state.loading = false;
        }
    }

    // ── Filtering ────────────────────────────────────────────────
    get filteredItems() {
        const items = (this.state.data && this.state.data.items) || [];
        const q = (this.state.search || "").trim().toLowerCase();
        const cat = this.state.category;
        return items.filter((it) => {
            if (cat !== "all" && it.category !== cat) return false;
            if (q) {
                const hay = [it.title, it.subtitle, it.state_label,
                             it.category_label].filter(Boolean).join(" ")
                                                             .toLowerCase();
                if (!hay.includes(q)) return false;
            }
            return true;
        });
    }

    get categoryChips() {
        const counts = (this.state.data && this.state.data.categories) || {};
        const total = (this.state.data && this.state.data.kpi
                       && this.state.data.kpi.total) || 0;
        const chips = [{ id: "all", label: _t("All"), count: total }];
        const order = [
            { id: "approval",   label: _t("Approvals"),  icon: "✅" },
            { id: "helpdesk",   label: _t("Helpdesk"),   icon: "🎫" },
            { id: "wms_count",  label: _t("WMS"),        icon: "📦" },
            { id: "kpi",        label: _t("KPI"),        icon: "🎯" },
            { id: "returns",    label: _t("Returns"),    icon: "↩" },
            { id: "ocr_review", label: _t("OCR"),        icon: "🧾" },
            { id: "field_svc",  label: _t("Field"),      icon: "🔧" },
            { id: "ai",         label: _t("AI"),         icon: "✨" },
            { id: "activities", label: _t("Activities"), icon: "📝" },
        ];
        for (const c of order) {
            if ((counts[c.id] || 0) > 0) {
                chips.push({ ...c, count: counts[c.id] });
            }
        }
        return chips;
    }

    // ── User actions ─────────────────────────────────────────────
    onSearchInput(ev) { this.state.search = ev.target.value; }
    selectCategory(catId) { this.state.category = catId; }

    async openItem(item) {
        if (!item.model || !item.res_id) return;
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: item.model,
            res_id: item.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    onManualRefresh() { this.refresh(false); }

    // ── Quick-create personal task ───────────────────────────────
    async quickCreateTask() {
        const name = this.state.quickCreate.name.trim();
        if (!name) return;
        this.state.creating = true;
        try {
            await this.orm.call(
                "kob.my.task.personal", "quick_create", [],
                {
                    name,
                    priority: this.state.quickCreate.priority || "1",
                    due_date: this.state.quickCreate.due_date || null,
                });
            this.state.quickCreate.name = "";
            this.state.quickCreate.due_date = "";
            this.notification.add(_t("เพิ่มงานสำเร็จ"), { type: "success" });
            await this.refresh(true);
        } catch (e) {
            this.notification.add(_t("ไม่สามารถสร้างงานได้"),
                                  { type: "danger" });
        } finally {
            this.state.creating = false;
        }
    }
    onQuickKeyDown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.quickCreateTask();
        }
    }

    // ── Helpers ──────────────────────────────────────────────────
    fmtTime(d) {
        if (!d) return "";
        const dt = new Date(d);
        return dt.toLocaleTimeString([], {
            hour: "2-digit", minute: "2-digit",
        });
    }
    fmtDate(s) {
        if (!s) return "";
        try {
            return new Date(s).toLocaleDateString([],
                { day: "numeric", month: "short" });
        } catch {
            return s;
        }
    }
}

registry.category("actions").add("kob_my_tasks.battle_board", MyBattleBoard);
