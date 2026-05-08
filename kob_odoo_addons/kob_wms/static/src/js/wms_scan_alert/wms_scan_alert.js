/** @odoo-module **/
/*
 * Shared scan-error alert utility.
 *
 * One call → full-screen flashing red overlay + alarm beeps (Web Audio API)
 * + vibration pattern. Use from ANY scan-handling screen so worker never
 * misses a wrong-SKU / duplicate / error response.
 *
 * Usage:
 *     import { triggerScanError, triggerScanSuccess } from
 *         "@kob_wms/js/wms_scan_alert/wms_scan_alert";
 *
 *     if (!result.ok) {
 *         triggerScanError(result.error || "Scan error");
 *         return;
 *     }
 *     triggerScanSuccess();
 */

let _audioCtx = null;
let _overlayEl = null;
let _overlayHideTimer = null;
let _toastEl = null;
let _toastHideTimer = null;

function _getAudioCtx() {
    if (_audioCtx) return _audioCtx;
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return null;
    try {
        _audioCtx = new Ctor();
    } catch (_) {
        _audioCtx = null;
    }
    return _audioCtx;
}

function _alarmBeep() {
    const ctx = _getAudioCtx();
    if (!ctx) return;
    try {
        // Resume context if suspended (Chrome autoplay policy after user gesture)
        if (ctx.state === "suspended") ctx.resume();
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
            gain.gain.linearRampToValueAtTime(0.35, start + 0.02);
            gain.gain.linearRampToValueAtTime(0.0, start + 0.15);
            osc.start(start);
            osc.stop(start + 0.16);
        });
    } catch (_) { /* swallow */ }
}

function _successBeep() {
    const ctx = _getAudioCtx();
    if (!ctx) return;
    try {
        if (ctx.state === "suspended") ctx.resume();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.type = "sine";
        osc.frequency.value = 1320;
        const start = ctx.currentTime;
        gain.gain.setValueAtTime(0.0, start);
        gain.gain.linearRampToValueAtTime(0.18, start + 0.01);
        gain.gain.linearRampToValueAtTime(0.0, start + 0.10);
        osc.start(start);
        osc.stop(start + 0.11);
    } catch (_) { /* swallow */ }
}

function _vibrate(pattern) {
    try { navigator.vibrate?.(pattern); } catch (_) { /* swallow */ }
}

function _ensureOverlay() {
    if (_overlayEl) return _overlayEl;
    _overlayEl = document.createElement("div");
    _overlayEl.className = "wms-scan-error-overlay";
    _overlayEl.setAttribute("aria-hidden", "true");
    _overlayEl.innerHTML =
        '<div class="wms-scan-error-card">' +
        '  <div class="wms-scan-error-icon">⚠</div>' +
        '  <div class="wms-scan-error-title">SCAN ERROR</div>' +
        '  <div class="wms-scan-error-msg"></div>' +
        '</div>';
    document.body.appendChild(_overlayEl);
    return _overlayEl;
}

function _ensureToast() {
    if (_toastEl) return _toastEl;
    _toastEl = document.createElement("div");
    _toastEl.className = "wms-scan-success-toast";
    _toastEl.setAttribute("aria-hidden", "true");
    _toastEl.textContent = "✓";
    document.body.appendChild(_toastEl);
    return _toastEl;
}

/**
 * Trigger the full-screen error alert.
 *
 * Effects (~1.6s):
 *  - Red overlay with white "SCAN ERROR" + message, flashes 3×
 *  - 4-tone 880/440 Hz alarm
 *  - Phone vibration: 4 short bursts
 *
 * @param {string} message Human-readable error from the RPC response.
 */
export function triggerScanError(message) {
    _alarmBeep();
    _vibrate([100, 50, 100, 50, 100, 50, 100]);
    const el = _ensureOverlay();
    const msgEl = el.querySelector(".wms-scan-error-msg");
    if (msgEl) msgEl.textContent = message || "Scan error";
    el.classList.remove("wms-scan-error-overlay--show");
    // Restart animation: force reflow before re-adding the class
    void el.offsetWidth;
    el.classList.add("wms-scan-error-overlay--show");
    clearTimeout(_overlayHideTimer);
    _overlayHideTimer = setTimeout(() => {
        el.classList.remove("wms-scan-error-overlay--show");
    }, 1600);
}

/**
 * Trigger the success cue — small green "✓" toast + soft beep + light vibration.
 * Subtle on purpose: scan throughput should not be slowed by visible UI.
 */
export function triggerScanSuccess() {
    _successBeep();
    _vibrate(40);
    const el = _ensureToast();
    el.classList.remove("wms-scan-success-toast--show");
    void el.offsetWidth;
    el.classList.add("wms-scan-success-toast--show");
    clearTimeout(_toastHideTimer);
    _toastHideTimer = setTimeout(() => {
        el.classList.remove("wms-scan-success-toast--show");
    }, 600);
}
