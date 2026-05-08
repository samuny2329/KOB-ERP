/** @odoo-module **/
import { Component, useState, useRef, onMounted, onPatched, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { Dialog } from "@web/core/dialog/dialog";
import { triggerScanError, triggerScanSuccess } from "@kob_wms/js/wms_scan_alert/wms_scan_alert";

// ── Close Box Dialog ──────────────────────────────────────────────────────────
/**
 * WmsCloseBoxDialog — auto-pops when all items are packed.
 * Shows the system-calculated recommended box, an override dropdown for
 * emergency cases, then closes the box and auto-prints the AWB.
 */
class WmsCloseBoxDialog extends Component {
    static template = "kob_wms.WmsCloseBoxDialog";
    static components = { Dialog };

    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");
        this.state  = useState({
            overrideCode: "",   // empty = use recommendation
            loading: false,
            error: "",
        });
    }

    /** Box code that will actually be used when closing. */
    get effectiveCode() {
        return this.state.overrideCode || (this.props.suggestion && this.props.suggestion.box_code) || "";
    }

    get effectiveLabel() {
        if (this.state.overrideCode) {
            const found = (this.props.boxes || []).find(b => b.code === this.state.overrideCode);
            return found ? found.label : this.state.overrideCode;
        }
        return (this.props.suggestion && this.props.suggestion.box_label) || "—";
    }

    onBoxChange(ev) {
        this.state.overrideCode = ev.target.value;
    }

    onCancel() {
        this.props.close();
    }

    async onCloseBox() {
        if (this.state.loading) return;
        this.state.loading = true;
        this.state.error   = "";

        try {
            const worker = (() => {
                try { return JSON.parse(localStorage.getItem("wms_worker") || "null") || {}; }
                catch { return {}; }
            })();

            const res = await this.orm.call(
                "wms.sales.order",
                "select_box_and_close",
                [[this.props.recordId], this.effectiveCode, worker.id || false]
            );

            if (!res.ok) {
                this.state.error   = res.error || "Unknown error";
                this.state.loading = false;
                return;
            }

            // Auto-print AWB if the backend returned a print action
            if (res.awb_action) {
                await this.action.doAction(res.awb_action);
            }

            this.props.close();
            // Navigate back to Pack Queue — worker is ready for next order
            await this.action.doAction("kob_wms.action_wms_pack_screen");

        } catch (err) {
            console.error("[WMS] close_box error:", err);
            this.state.error   = "Server error — see console";
            this.state.loading = false;
        }
    }
}

// ── Scan Bar Widget ───────────────────────────────────────────────────────────
/**
 * WmsScanBar — Odoo view_widget placed at the top of the order form sheet.
 *
 * Single-SO mode (default):
 *   • Worker scans a SKU/barcode → routed to action_scan_item which delegates
 *     to scan_pick / scan_pack based on order status.
 *   • When packing is complete → auto-opens WmsCloseBoxDialog.
 *
 * Multi-SO merge mode (NEW):
 *   • Worker on the form scans ANOTHER order's ref → that SO is merged into
 *     this form. A consolidated panel appears above the standard Items
 *     table (which is hidden) showing all merged SOs and their lines tagged
 *     with origin SO. Subsequent SKU scans distribute FIFO across all
 *     merged SOs via wms.sales.order.queue_scan_dispatch.
 *   • Scanning the same merged SO again toggles it OUT of the merge.
 *   • Esc / "CLEAR" / "RESET" / "C" clears the merge → form returns to
 *     single-SO mode.
 *   • Merge state persists in localStorage keyed by primary record id, so
 *     a refresh or navigate-away preserves it.
 */
class WmsScanBar extends Component {
    static template = "kob_wms.WmsScanBar";
    // No strict static props — Widget wrapper passes dynamic props

    setup() {
        this.orm    = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.inputRef  = useRef("scanInput");
        this.statusRef = useRef("scanStatus");
        this._refocus  = false;
        this._panelEl  = null;
        this._tableHiddenEl = null;

        onMounted(() => {
            this._focus();
            this._renderMergePanel();
        });
        onPatched(() => {
            if (this._refocus) {
                this._refocus = false;
                this._focus();
            }
            this._renderMergePanel();
        });
        onWillUnmount(() => {
            this._removePanel();
            this._showStandardTable();
        });
    }

    _focus() {
        requestAnimationFrame(() => this.inputRef.el?.focus());
    }

    // ── Merge state (browser localStorage, keyed by primary record id) ──
    _mergeKey() {
        const rid = this.props.record?.resId;
        return rid ? `wms_form_merge_${rid}` : null;
    }
    _loadMerge() {
        const key = this._mergeKey();
        if (!key) return [];
        try {
            const arr = JSON.parse(localStorage.getItem(key) || "[]");
            return Array.isArray(arr) ? arr.map(Number).filter(Boolean) : [];
        } catch (_e) {
            return [];
        }
    }
    _saveMerge(ids) {
        const key = this._mergeKey();
        if (!key) return;
        localStorage.setItem(key, JSON.stringify(ids));
    }
    _clearMerge() {
        const key = this._mergeKey();
        if (key) localStorage.removeItem(key);
    }

    async onKeydown(ev) {
        if (ev.key === "Escape") {
            // Esc clears the merge panel without leaving the form.
            const merge = this._loadMerge();
            if (merge.length) {
                ev.preventDefault();
                this._clearMerge();
                this._setStatus("✓ Merge cleared", "wms-scan-found");
                await this._renderMergePanel();
                this._scheduleReset();
            }
            return;
        }
        if (ev.key !== "Enter") return;

        const val = ev.target.value.trim();
        if (!val) return;
        ev.target.value = "";

        // Special clear keywords
        const kw = val.toUpperCase();
        if (kw === "CLEAR" || kw === "RESET") {
            this._clearMerge();
            this._setStatus("✓ Merge cleared", "wms-scan-found");
            await this._renderMergePanel();
            this._scheduleReset();
            return;
        }

        this._setStatus("SCANNING...", "wms-scan-searching");

        try {
            const recordId = this.props.record.resId;
            if (!recordId) {
                this._flash("SAVE ORDER FIRST", "wms-scan-error");
                return;
            }

            const worker = (() => {
                try { return JSON.parse(localStorage.getItem("wms_worker") || "null") || {}; }
                catch { return {}; }
            })();

            // ── Step 1: see if barcode resolves to an SO ref ──────────
            //   `resolve_so_ref(code)` is the public RPC wrapper that
            //   returns an id or False.
            let resolvedId = null;
            try {
                const r = await this.orm.call(
                    "wms.sales.order",
                    "resolve_so_ref",
                    [val],
                );
                if (typeof r === "number" && r > 0) {
                    resolvedId = r;
                }
            } catch (err) {
                console.warn("[WMS] resolve_so_ref failed:", err);
                resolvedId = null;
            }

            // SO branch — toggle merge
            if (resolvedId) {
                if (resolvedId === recordId) {
                    this._setStatus("↺ already open", "wms-scan-searching");
                    this._scheduleReset();
                    return;
                }
                let merge = this._loadMerge();
                if (merge.includes(resolvedId)) {
                    merge = merge.filter((i) => i !== resolvedId);
                    this._saveMerge(merge);
                    this._setStatus(`− ปิด SO #${resolvedId}`, "wms-scan-searching");
                } else {
                    merge.push(resolvedId);
                    this._saveMerge(merge);
                    this._setStatus(
                        `+ เพิ่ม SO #${resolvedId} (รวม ${merge.length + 1} ใบ)`,
                        "wms-scan-found",
                    );
                }
                await this._renderMergePanel();
                this._scheduleReset();
                return;
            }

            // ── Step 2: SKU branch ────────────────────────────────────
            const merge = this._loadMerge();

            if (!merge.length) {
                // Single-order classic flow — UNCHANGED behaviour
                const res = await this.orm.call(
                    "wms.sales.order",
                    "action_scan_item",
                    [[recordId], val, worker.id || false],
                );

                if (!res.ok) {
                    triggerScanError(res.error || "Scan error");
                    this._flash(`✗  ${res.error}`, "wms-scan-error");
                    return;
                }
                triggerScanSuccess();

                if (res.all_done && res.phase === "pack") {
                    this._setStatus("✓ PACKING COMPLETE — Select box...", "wms-scan-found");
                    await this.props.record.load();
                    await this._openCloseBoxDialog(recordId);
                    this._scheduleReset();
                    return;
                }

                if (res.all_done && res.phase === "pick") {
                    this._setStatus("✓ ALL PICKED  —  Returning to queue...", "wms-scan-found");
                    await this.props.record.load();
                    setTimeout(() => {
                        this.action.doAction("kob_wms.action_wms_pick_screen");
                    }, 1500);
                    return;
                }

                this._setStatus(`✓ ${res.msg}`, "wms-scan-found");
                this._refocus = true;
                await this.props.record.load();
                this._scheduleReset();
                return;
            }

            // Merge-mode SKU — distribute via orchestrator
            const activeIds = [recordId, ...merge];
            const dispatch = await this.orm.call(
                "wms.sales.order",
                "queue_scan_dispatch",
                [activeIds, val, worker.id || false],
            );

            if (!dispatch || dispatch.type === "error" || dispatch.type === "so_invalid") {
                triggerScanError(dispatch?.error || "Unknown");
                this._flash(`✗  ${dispatch?.error || "Unknown"}`, "wms-scan-error");
                return;
            }
            if (dispatch.type === "pick") {
                this._setStatus(
                    `✓ ${dispatch.product_name} → ${dispatch.order_name}`
                    + (dispatch.all_picked_in_order ? " [DONE]" : ""),
                    "wms-scan-found",
                );
                await this.props.record.load();
                await this._renderMergePanel(dispatch.line_id);
                if (dispatch.all_done_in_basket) {
                    this._setStatus(
                        "✓ ทุกใบงานครบ — กลับ Pick Queue",
                        "wms-scan-found",
                    );
                    this._clearMerge();
                    setTimeout(() => {
                        this.action.doAction("kob_wms.action_wms_pick_screen");
                    }, 1500);
                    return;
                }
                this._scheduleReset();
                return;
            }
            // Fallback for unexpected response shape
            this._flash("✗  Unknown response", "wms-scan-error");

        } catch (err) {
            console.error("[WMS] scan_item error:", err);
            this._flash("RPC ERROR — see console", "wms-scan-error");
        }
    }

    // ── Merge panel rendering ───────────────────────────────────────────
    async _renderMergePanel(highlightLineId = null) {
        const merge = this._loadMerge();
        const recordId = this.props.record?.resId;

        // No primary record yet (new draft): nothing to render
        if (!recordId) {
            this._removePanel();
            this._showStandardTable();
            return;
        }

        if (!merge.length) {
            this._removePanel();
            this._showStandardTable();
            return;
        }

        const allIds = [recordId, ...merge];

        let orders = [];
        let lines = [];
        try {
            [orders, lines] = await Promise.all([
                this.orm.searchRead(
                    "wms.sales.order",
                    [["id", "in", allIds]],
                    ["display_order_name", "customer", "platform",
                     "picked_total", "expected_total",
                     "all_picked", "status"],
                ),
                this.orm.searchRead(
                    "wms.sales.order.line",
                    [["order_id", "in", allIds],
                     ["is_service", "=", false]],
                    ["id", "order_id", "sku", "product_name",
                     "expected_qty", "picked_qty",
                     "product_barcode"],
                    { order: "sku, sequence, id" },
                ),
            ]);
        } catch (_e) {
            return;
        }

        const orderMap = Object.fromEntries(orders.map((o) => [o.id, o]));

        // Order display list — primary first, then merge order
        const palette = [
            "#00a99d", "#5b6bf3", "#f59e0b",
            "#ef4444", "#10b981", "#a855f7",
            "#0ea5e9", "#ec4899", "#84cc16",
        ];
        const tagColor = {};
        allIds.forEach((id, idx) => {
            tagColor[id] = palette[idx % palette.length];
        });

        const totExp = orders.reduce((a, o) => a + (o.expected_total || 0), 0);
        const totPicked = orders.reduce((a, o) => a + (o.picked_total || 0), 0);
        const pct = totExp ? Math.round((totPicked / totExp) * 100) : 0;

        // Sort lines: by SKU, then by primary→merge order
        const rank = Object.fromEntries(allIds.map((id, idx) => [id, idx]));
        const orderIdOf = (l) => Array.isArray(l.order_id) ? l.order_id[0] : l.order_id;
        const sortedLines = [...lines].sort((a, b) => {
            const ska = (a.sku || "").localeCompare(b.sku || "");
            if (ska !== 0) return ska;
            return (rank[orderIdOf(a)] ?? 99) - (rank[orderIdOf(b)] ?? 99);
        });

        // Build / update panel
        if (!this._panelEl || !document.body.contains(this._panelEl)) {
            this._panelEl = document.createElement("div");
            this._panelEl.className = "wms-form-merge-panel";
            // Insert at the top of the form sheet, just below the scan bar.
            const scanBar = document.querySelector(".o_form_sheet .wms-scan-bar")
                          || document.querySelector(".wms-scan-bar");
            if (scanBar) {
                scanBar.insertAdjacentElement("afterend", this._panelEl);
            } else {
                document.querySelector(".o_form_sheet")?.prepend(this._panelEl);
            }
        }

        const subBadgesHtml = orders
            .filter((o) => o.id !== recordId)
            .map((o) => {
                const c = tagColor[o.id] || "#00a99d";
                const done = o.all_picked ? " is-done" : "";
                return `<span class="wms-merge-sub-badge${done}" style="background:${c}">
                    <span>${this._esc(o.display_order_name)}</span>
                    <span class="wms-merge-sub-qty">${o.picked_total}/${o.expected_total}</span>
                </span>`;
            }).join("");

        const linesHtml = sortedLines.map((l) => {
            const oid = orderIdOf(l);
            const o = orderMap[oid];
            const c = tagColor[oid] || "#00a99d";
            const code = l.product_barcode || l.sku || "";
            const pickedAll = l.picked_qty >= l.expected_qty;
            const remaining = Math.max(0, l.expected_qty - l.picked_qty);
            const linePct = l.expected_qty
                ? Math.round((l.picked_qty / l.expected_qty) * 100)
                : 0;
            const flash = highlightLineId && Number(l.id) === Number(highlightLineId)
                ? " is-flash" : "";
            return `
                <tr class="wms-merge-line${pickedAll ? " is-done" : ""}${flash}">
                    <td class="wms-merge-tag-col">
                        <span class="wms-merge-tag" style="background:${c}">
                            ${this._esc(o ? o.display_order_name : "?")}
                        </span>
                    </td>
                    <td class="wms-merge-sku">
                        <code>${this._esc(l.sku || "")}</code>
                        ${code && code !== l.sku
                            ? `<small class="text-muted ms-1">${this._esc(code)}</small>`
                            : ""}
                    </td>
                    <td class="wms-merge-product">${this._esc(l.product_name || "")}</td>
                    <td class="wms-merge-qty">
                        <span class="wms-merge-picked">${l.picked_qty}</span>
                        <span class="wms-merge-sep">/</span>
                        <span class="wms-merge-exp">${l.expected_qty}</span>
                    </td>
                    <td class="wms-merge-progress">
                        <div class="wms-merge-bar">
                            <div class="wms-merge-fill" style="width:${linePct}%"></div>
                        </div>
                        <small class="text-muted">${remaining > 0 ? `เหลือ ${remaining}` : "✓ ครบ"}</small>
                    </td>
                </tr>
            `;
        }).join("");

        const primary = orderMap[recordId];
        const primaryRef = primary ? primary.display_order_name : "—";

        this._panelEl.innerHTML = `
            <div class="wms-form-merge-head">
                <div class="wms-form-merge-title">
                    <i class="fa fa-clone"></i>
                    <span>Multi-Order Pick:</span>
                    <span class="wms-form-merge-primary">${this._esc(primaryRef)}</span>
                    <span class="wms-form-merge-count">+ ${merge.length} ใบ</span>
                </div>
                <div class="wms-form-merge-progress">
                    <span class="wms-form-merge-qty">${totPicked}/${totExp}</span>
                    <div class="wms-form-merge-progress-bar">
                        <div class="wms-form-merge-progress-fill" style="width:${pct}%"></div>
                    </div>
                    <span class="wms-form-merge-pct">${pct}%</span>
                </div>
                <div class="wms-form-merge-subs">
                    ${subBadgesHtml}
                </div>
                <div class="wms-form-merge-hint">
                    ยิง SO เดิมซ้ำ → ลบใบนั้น · กด Esc หรือพิมพ์ <code>CLEAR</code> → ปิด merge ทั้งหมด
                </div>
            </div>
            <table class="wms-form-merge-table">
                <thead>
                    <tr>
                        <th>SO</th>
                        <th>SKU</th>
                        <th>Product</th>
                        <th>Qty</th>
                        <th>Progress</th>
                    </tr>
                </thead>
                <tbody>
                    ${linesHtml || '<tr><td colspan="5" class="text-muted text-center">— ไม่มีไลน์ที่ต้อง pick —</td></tr>'}
                </tbody>
            </table>
        `;

        this._hideStandardTable();
    }

    _removePanel() {
        if (this._panelEl) {
            this._panelEl.remove();
            this._panelEl = null;
        }
    }

    _hideStandardTable() {
        // Hide the standard line_ids table (and the totals group right below it)
        // while merge panel is showing — worker should focus on merged view.
        const table = document.querySelector(
            ".o_form_sheet .o_field_widget[name='line_ids']"
        );
        if (table) {
            table.style.display = "none";
            this._tableHiddenEl = table;
        }
    }

    _showStandardTable() {
        if (this._tableHiddenEl) {
            this._tableHiddenEl.style.display = "";
            this._tableHiddenEl = null;
        }
        // Defensive: also unhide any line_ids field in current DOM
        document
            .querySelectorAll(".o_form_sheet .o_field_widget[name='line_ids']")
            .forEach((el) => { el.style.display = ""; });
    }

    _esc(s) {
        return String(s || "").replace(/[<>&"']/g, (c) => ({
            "<": "&lt;", ">": "&gt;", "&": "&amp;",
            '"': "&quot;", "'": "&#39;",
        }[c]));
    }

    async _openCloseBoxDialog(recordId) {
        try {
            const data = await this.orm.call(
                "wms.sales.order",
                "action_get_close_box_data",
                [[recordId]]
            );

            this.dialog.add(WmsCloseBoxDialog, {
                recordId:   recordId,
                record:     this.props.record,
                orderName:  data.order_name,
                suggestion: data.suggestion,
                boxes:      data.boxes || [],
            });
        } catch (err) {
            console.error("[WMS] get_close_box_data error:", err);
            this._setStatus("Could not load box data", "wms-scan-error");
            this._scheduleReset();   // ← reset to READY after 1.8s so worker is not stuck
        }
    }

    _setStatus(text, cls) {
        const el = this.statusRef.el;
        if (!el) return;
        el.textContent = text;
        el.className   = `wms-scan-status ${cls}`;
    }

    _flash(msg, cls) {
        this._setStatus(msg, cls);
        this._scheduleReset();
    }

    _scheduleReset() {
        setTimeout(() => {
            this._setStatus("READY", "wms-scan-ready");
            this._focus();
        }, 1800);
    }
}

// Odoo 18: view_widgets registry expects { component } object
registry.category("view_widgets").add("wms_scan_bar", { component: WmsScanBar });
