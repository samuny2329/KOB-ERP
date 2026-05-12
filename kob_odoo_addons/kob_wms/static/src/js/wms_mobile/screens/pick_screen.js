/** @odoo-module **/
// =====================================================================
// Pick Screen — list (Account-Report style table) + detail (POS-style)
// =====================================================================

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const ORDER_FIELDS = [
    "id", "name", "so_name", "ref", "awb", "display_order_name", "box_barcode",
    "customer", "platform", "status",
    "expected_total", "picked_total", "packed_total", "sla_status",
    "all_picked", "all_packed",
];
const LINE_FIELDS = [
    "id", "sku", "product_name", "expected_qty", "picked_qty", "packed_qty",
];

export class PickScreen extends Component {
    static template = "kob_wms.MobilePickScreen";
    static props = {
        worker: Object,
        op: Object,
        currentOrderId: { type: [Number, { value: null }], optional: true },
        onBack: Function,
        onSelectOrder: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            // List view
            orders: [],
            search: "",
            platformFilter: "all",
            collapsedGroups: {},
            loadingList: false,
            // Detail view
            currentOrder: null,
            currentLines: [],
            scanValue: "",
            loadingDetail: false,
            // Basket (multi-pick session) — scan AWB/ref to add, then rapid-
            // fire SKU scans dispatch to whichever basket order needs them.
            // basket entry: {id, name, ref, awb, customer, platform,
            //                lines: [{id,sku,product_name,expected_qty,picked_qty}],
            //                all_picked, expected_total, picked_total,
            //                flashSuccess}
            basket: [],
            basketActiveId: null,    // most-recently-touched order (highlight)
            // Recent scans
            history: [],
            // UX feedback
            flashError: false,        // red overlay on scan fail
            flashSuccess: false,      // green pulse on scan ok
            errorMsg: "",             // shown in scan bar on error
            autoDoneCountdown: 0,     // seconds remaining before auto-confirm
        });

        this.scanRef = useRef("scan");
        this.listScanRef = useRef("listScan");

        onMounted(() => {
            if (this.props.currentOrderId) {
                this.loadOrderDetail(this.props.currentOrderId);
            } else {
                this.loadList();
            }
            // Keep scan input focused — handheld scanners type into the focused
            // element. If user taps elsewhere, refocus within 250ms so the
            // cursor is always blinking in the scan field. Switches target
            // automatically: list view → listScanRef, detail view → scanRef.
            this._focusKeeper = setInterval(() => {
                if (this.state.showBoxPicker) return;     // pack only
                // Priority: detail-view scan > list-view scan (used by both
                // legacy single-drill flow and the new basket multi-pick).
                const target = this.state.currentOrder
                    ? this.scanRef.el
                    : this.listScanRef.el;
                if (!target) return;
                const active = document.activeElement;
                // Don't steal focus from other text inputs (search, etc.)
                if (active && active !== target && (
                    active.tagName === "INPUT" || active.tagName === "TEXTAREA"
                )) return;
                if (active !== target) target.focus();
            }, 250);
        });
        onWillUnmount(() => {
            clearInterval(this._focusKeeper);
            clearInterval(this._autoDoneTimer);
        });
    }

    // ── LIST VIEW ─────────────────────────────────────────────────────
    async loadList() {
        this.state.loadingList = true;
        try {
            const domain = [["status", "in", this.props.op.statusFilter]];
            const orders = await this.orm.searchRead(
                "wms.sales.order", domain, ORDER_FIELDS,
                { order: "create_date desc", limit: 200 },
            );
            this.state.orders = orders;
        } catch (e) {
            console.error("[KOB Mobile Pick] loadList", e);
            this.notification.add("โหลดรายการไม่สำเร็จ", { type: "danger" });
        } finally {
            this.state.loadingList = false;
        }
    }

    get filteredOrders() {
        let list = this.state.orders;
        const q = this.state.search.trim().toLowerCase();
        if (q) {
            list = list.filter(o =>
                (o.ref || "").toLowerCase().includes(q) ||
                (o.name || "").toLowerCase().includes(q) ||
                (o.so_name || "").toLowerCase().includes(q) ||
                (o.awb || "").toLowerCase().includes(q) ||
                (o.display_order_name || "").toLowerCase().includes(q) ||
                (o.box_barcode || "").toLowerCase().includes(q) ||
                (o.customer || "").toLowerCase().includes(q)
            );
        }
        if (this.state.platformFilter !== "all") {
            list = list.filter(o => (o.platform || "").toLowerCase().includes(this.state.platformFilter));
        }
        return list;
    }

    get groupedOrders() {
        // Group by platform — Account Report-style hierarchical display
        const groups = {};
        for (const o of this.filteredOrders) {
            const plat = this.platformKey(o.platform);
            if (!groups[plat]) groups[plat] = { key: plat, label: this.platformLabel(o.platform), orders: [] };
            groups[plat].orders.push(o);
        }
        return Object.values(groups).sort((a, b) => b.orders.length - a.orders.length);
    }

    get totals() {
        const list = this.filteredOrders;
        const totalSku = list.reduce((s, o) => s + (o.expected_total || 0), 0);
        const breached = list.filter(o => o.sla_status === "breached").length;
        return {
            orders: list.length,
            skus: totalSku,
            breached,
        };
    }

    platformKey(platform) {
        if (!platform) return "manual";
        const p = platform.toLowerCase();
        if (p.includes("shopee")) return "shopee";
        if (p.includes("tiktok")) return "tiktok";
        if (p.includes("lazada")) return "lazada";
        if (p.includes("pos"))    return "pos";
        if (p.includes("odoo"))   return "odoo";
        return "manual";
    }
    platformLabel(platform) {
        const k = this.platformKey(platform);
        return ({
            shopee: "Shopee",
            tiktok: "TikTok",
            lazada: "Lazada",
            pos: "POS",
            odoo: "Odoo",
            manual: "Manual",
        })[k];
    }

    toggleGroup(key) {
        this.state.collapsedGroups[key] = !this.state.collapsedGroups[key];
    }

    setSearch(ev) {
        this.state.search = ev.target.value;
    }

    /**
     * List-level scan = basket multi-pick driver.
     *
     * Worker scans into the bar at the top of the queue:
     *   - barcode = order ref / AWB / SO name  → add order to basket
     *   - barcode = product SKU / EAN          → dispatch +1 to the first
     *     basket order that still needs it (FIFO by sale_order_date)
     *   - duplicate AWB                         → soft warn (no alarm)
     *   - unknown                               → alarm beep + chip
     *
     * Backend orchestrator: ``wms.sales.order.queue_scan_dispatch``
     * ([wms_sales_order.py:844](../../models/wms_sales_order.py:844))
     */
    async onListScan(ev) {
        if (ev.key !== "Enter") return;
        const code = (this.state.search || "").trim();
        if (!code) return;

        const resetBar = () => {
            this.state.search = "";
            const el = this.listScanRef?.el;
            if (el) { el.value = ""; el.focus(); }
        };

        const activeIds = this.state.basket.map(o => o.id);
        let result;
        try {
            result = await this.orm.call(
                "wms.sales.order", "queue_scan_dispatch",
                [[], activeIds, code, this.props.worker?.id || null],
            );
        } catch (e) {
            console.error("[KOB Mobile Pick] queue_scan_dispatch", e);
            resetBar();
            this._listScanError(`Scan error: ${e.message || e}`);
            return;
        }

        resetBar();

        switch ((result || {}).type) {
            case "so_added":
                await this._addToBasket(result.order_id);
                this._listScanSuccess(`+ ${result.order_name}`);
                this.state.basketActiveId = result.order_id;
                break;
            case "so_duplicate":
                // Already in basket — flash that card but no alarm.
                this.state.basketActiveId = result.order_id;
                this._flashBasketEntry(result.order_id);
                this.notification.add(
                    `${result.order_name} อยู่ใน basket แล้ว`,
                    { type: "warning" },
                );
                this._beep(true);
                break;
            case "so_invalid":
                this._listScanError(result.error || "Order ไม่พร้อม pick");
                break;
            case "pick":
                this.state.basketActiveId = result.order_id;
                await this._updateBasketOrder(result.order_id);
                this._listScanSuccess(`${result.product_name}`);
                this._flashBasketEntry(result.order_id);
                if (result.all_done_in_basket) {
                    this._basketComplete();
                }
                break;
            case "error":
            default:
                this._listScanError(
                    (result && result.error) || "Scan ไม่สำเร็จ",
                );
                break;
        }
    }

    // ── BASKET HELPERS ────────────────────────────────────────────────
    async _addToBasket(orderId) {
        try {
            const [order] = await this.orm.read(
                "wms.sales.order", [orderId], ORDER_FIELDS,
            );
            if (!order) return;
            const lines = await this.orm.searchRead(
                "wms.sales.order.line",
                [["order_id", "=", orderId]],
                LINE_FIELDS,
            );
            // Keep first 5 to avoid wide overflow — strip can still scroll.
            this.state.basket.push({
                id: order.id,
                name: order.name,
                ref: order.ref,
                awb: order.awb,
                so_name: order.so_name,
                display_order_name: order.display_order_name,
                customer: order.customer,
                platform: order.platform,
                status: order.status,
                expected_total: order.expected_total || 0,
                picked_total: order.picked_total || 0,
                all_picked: !!order.all_picked,
                lines,
                flashSuccess: false,
            });
        } catch (e) {
            console.error("[KOB Mobile Pick] _addToBasket", e);
            this.notification.add("โหลดใบ pick ไม่สำเร็จ", { type: "danger" });
        }
    }

    async _updateBasketOrder(orderId) {
        const entry = this.state.basket.find(o => o.id === orderId);
        if (!entry) return;
        try {
            const [order] = await this.orm.read(
                "wms.sales.order", [orderId], ORDER_FIELDS,
            );
            const lines = await this.orm.searchRead(
                "wms.sales.order.line",
                [["order_id", "=", orderId]],
                LINE_FIELDS,
            );
            if (order) {
                entry.picked_total = order.picked_total || 0;
                entry.expected_total = order.expected_total || 0;
                entry.all_picked = !!order.all_picked;
                entry.status = order.status;
            }
            entry.lines = lines;
        } catch (e) {
            console.error("[KOB Mobile Pick] _updateBasketOrder", e);
        }
    }

    removeFromBasket(orderId) {
        this.state.basket = this.state.basket.filter(o => o.id !== orderId);
        if (this.state.basketActiveId === orderId) {
            this.state.basketActiveId = this.state.basket[0]?.id || null;
        }
    }

    clearBasket() {
        this.state.basket = [];
        this.state.basketActiveId = null;
    }

    _basketComplete() {
        // All orders in the basket reached 100% — celebrate + clear.
        this._beep(true);
        this._vibrate([60, 40, 60, 40, 120]);
        this.notification.add("✓ Basket picked complete", { type: "success" });
        // Hold cards on screen 1.2s so worker can see the green flash,
        // then clear so they can start the next batch.
        setTimeout(() => {
            this.clearBasket();
            this.loadList();
        }, 1200);
    }

    _flashBasketEntry(orderId) {
        const entry = this.state.basket.find(o => o.id === orderId);
        if (!entry) return;
        entry.flashSuccess = true;
        clearTimeout(entry._flashTimer);
        entry._flashTimer = setTimeout(() => {
            entry.flashSuccess = false;
        }, 600);
    }

    _listScanSuccess(label) {
        this._beep(true);
        this._vibrate(40);
        this.state.flashSuccess = true;
        this.state.errorMsg = "";
        clearTimeout(this._successTimer);
        this._successTimer = setTimeout(() => {
            this.state.flashSuccess = false;
        }, 500);
        if (label) {
            this.state.history.unshift({ ts: Date.now(), sku: label });
            if (this.state.history.length > 10) this.state.history.pop();
        }
    }

    _listScanError(msg) {
        this._alarmBeep();
        this._vibrate([100, 50, 100, 50, 100]);
        this.state.errorMsg = msg;
        this.state.flashError = true;
        const el = this.listScanRef?.el;
        if (el) {
            el.value = "";
            el.focus();
        }
        this.notification.add(msg, { type: "danger", title: "❌ SCAN ERROR" });
        clearTimeout(this._flashTimer);
        this._flashTimer = setTimeout(() => {
            this.state.flashError = false;
            this.state.errorMsg = "";
        }, 1600);
    }

    setPlatformFilter(p) {
        this.state.platformFilter = p;
    }

    // ── DETAIL VIEW ───────────────────────────────────────────────────
    async loadOrderDetail(orderId) {
        this.state.loadingDetail = true;
        try {
            const orders = await this.orm.read("wms.sales.order", [orderId], ORDER_FIELDS);
            this.state.currentOrder = orders[0] || null;
            if (this.state.currentOrder) {
                const lines = await this.orm.searchRead(
                    "wms.sales.order.line",
                    [["order_id", "=", orderId]],
                    LINE_FIELDS,
                );
                this.state.currentLines = lines;
            }
            this.props.onSelectOrder(orderId);
            // Auto-focus scan input
            setTimeout(() => this.scanRef.el?.focus(), 100);
        } catch (e) {
            console.error("[KOB Mobile Pick] loadOrderDetail", e);
            this.notification.add("โหลดรายละเอียดไม่สำเร็จ", { type: "danger" });
        } finally {
            this.state.loadingDetail = false;
        }
    }

    closeDetail() {
        this.state.currentOrder = null;
        this.state.currentLines = [];
        this.state.scanValue = "";
        this.props.onSelectOrder(null);
        this.loadList();
    }

    async onScan(ev) {
        if (ev.key !== "Enter") return;
        const code = (this.state.scanValue || "").trim().toUpperCase();
        if (!code) return;

        const order = this.state.currentOrder;
        if (!order) return;

        // Client-side qty pre-check ONLY when the scanned code matches a line
        // by SKU exactly. Skip this when code looks like a product barcode/EAN
        // (server scan_pick matches SKU + default_code + product.barcode, so
        // we cannot reliably resolve those client-side).
        const skuMatch = this.state.currentLines.find(
            l => (l.sku || "").toUpperCase() === code
        );
        if (skuMatch && (skuMatch.picked_qty || 0) >= (skuMatch.expected_qty || 0)) {
            this._scanError(`${skuMatch.sku} ครบแล้ว (${skuMatch.picked_qty}/${skuMatch.expected_qty})`);
            return;
        }

        try {
            const result = await this.orm.call(
                "wms.sales.order", "scan_pick",
                [[order.id], code, this.props.worker?.id || null],
            );
            if (result && result.ok === false) {
                this._scanError(result.error || "Scan ไม่สำเร็จ");
                return;
            }
            // Success — server may have resolved code → product → SKU.
            // Refresh lines to capture the increment on whichever line matched.
            await this._reloadLines();
            // Find the line that actually got incremented for success feedback.
            const feedbackLine = skuMatch
                || this.state.currentLines.find(l => l.picked_qty > (this._prevPicked?.[l.id] || 0));
            this._scanSuccess(feedbackLine || { sku: code });

            // ── AUTO-DONE: detect when all items reach expected qty ──────
            if (this.progressPct >= 100) {
                this._startAutoDone();
            }
        } catch (e) {
            console.error("[KOB Mobile Pick] scan", e);
            this._scanError("Scan error: " + (e.message || e));
        }
    }

    _scanError(msg) {
        // DRAMATIC error: rapid alarm beeps + long vibration pattern
        this._alarmBeep();
        this._vibrate([100, 50, 100, 50, 100, 50, 100]);  // 4× short bursts
        this.state.errorMsg = msg;
        this.state.flashError = true;
        this.state.scanValue = "";
        // Hard-reset DOM value + refocus instantly so the next scan goes in.
        // OWL re-render alone can lag a frame and the scanner may emit the
        // next keystroke before the input is cleared — leaving stale chars.
        const el = this.scanRef?.el;
        if (el) {
            el.value = "";
            el.focus();
        }
        this.notification.add(msg, { type: "danger", title: "❌ SCAN ERROR" });

        clearTimeout(this._flashTimer);
        this._flashTimer = setTimeout(() => {
            this.state.flashError = false;
            this.state.errorMsg = "";
        }, 1600);
    }

    _alarmBeep() {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            // 4 alternating high-low alarm tones
            const tones = [880, 440, 880, 440];
            tones.forEach((freq, i) => {
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.type = "square";
                osc.frequency.value = freq;
                const start = ctx.currentTime + i * 0.18;
                gain.gain.setValueAtTime(0.0, start);
                gain.gain.linearRampToValueAtTime(0.25, start + 0.02);
                gain.gain.linearRampToValueAtTime(0.0,  start + 0.15);
                osc.start(start);
                osc.stop(start + 0.16);
            });
        } catch (_) { /* no audio */ }
    }

    _scanSuccess(line) {
        this._beep(true);
        this._vibrate(40);
        this.state.history.unshift({ ts: Date.now(), sku: line.sku, name: line.product_name });
        if (this.state.history.length > 10) this.state.history.pop();
        this.state.scanValue = "";
        this.state.errorMsg = "";
        this.state.flashSuccess = true;
        clearTimeout(this._successTimer);
        this._successTimer = setTimeout(() => {
            this.state.flashSuccess = false;
        }, 600);
    }

    _startAutoDone() {
        // Show 3-second countdown then auto-confirm
        let remaining = 3;
        this.state.autoDoneCountdown = remaining;
        clearInterval(this._autoDoneTimer);
        this._autoDoneTimer = setInterval(() => {
            remaining -= 1;
            this.state.autoDoneCountdown = remaining;
            if (remaining <= 0) {
                clearInterval(this._autoDoneTimer);
                this.confirmPick();
            }
        }, 1000);
    }

    cancelAutoDone() {
        clearInterval(this._autoDoneTimer);
        this.state.autoDoneCountdown = 0;
    }

    async _reloadLines() {
        const order = this.state.currentOrder;
        if (!order) return;
        const lines = await this.orm.searchRead(
            "wms.sales.order.line",
            [["order_id", "=", order.id]],
            LINE_FIELDS,
        );
        this.state.currentLines = lines;
        // Refresh order header to capture status changes
        const orders = await this.orm.read("wms.sales.order", [order.id], ORDER_FIELDS);
        if (orders[0]) {
            Object.assign(this.state.currentOrder, orders[0]);
        }
    }

    async confirmPick() {
        // When all picked, status auto-transitions to 'picked' on server.
        // This button just navigates back to list (state already saved on each scan).
        const order = this.state.currentOrder;
        if (!order) return;
        if (this.progressPct >= 100) {
            this.notification.add(`✓ ${order.ref || order.name} picked complete`, { type: "success" });
        } else {
            this.notification.add(`Saved partial pick: ${order.ref || order.name}`, { type: "info" });
        }
        this.closeDetail();
    }

    get progressPct() {
        const lines = this.state.currentLines;
        const total = lines.reduce((s, l) => s + (l.expected_qty || 0), 0);
        const done  = lines.reduce((s, l) => s + Math.min(l.picked_qty || 0, l.expected_qty || 0), 0);
        if (!total) return 0;
        return Math.round(done / total * 100);
    }

    _beep(success) {
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = success ? 880 : 300;
            gain.gain.setValueAtTime(0.15, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.15);
            osc.start();
            osc.stop(ctx.currentTime + 0.15);
        } catch (_) { /* no audio */ }
    }
    _vibrate(ms) {
        try { navigator.vibrate?.(ms); } catch (_) { /* no vibrate */ }
    }
}
