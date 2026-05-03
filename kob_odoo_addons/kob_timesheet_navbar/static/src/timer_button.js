/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";

const STORAGE_KEY = "kob.timesheet.timer.state";

export class KobTimesheetTimerButton extends Component {
    static template = "kob_timesheet_navbar.TimerButton";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            running: false,
            startTime: null,
            description: "",
            elapsed: 0,
        });
        this._tickHandle = null;

        onWillStart(() => this._restoreFromStorage());
        onWillUnmount(() => this._stopTick());
    }

    _restoreFromStorage() {
        try {
            const raw = browser.localStorage.getItem(STORAGE_KEY);
            if (!raw) return;
            const data = JSON.parse(raw);
            if (data && data.running && data.startTime) {
                this.state.running = true;
                this.state.startTime = data.startTime;
                this.state.description = data.description || "";
                this._startTick();
            }
        } catch (e) {
            console.warn("[KobTimer] restore failed", e);
        }
    }

    _persist() {
        const data = {
            running: this.state.running,
            startTime: this.state.startTime,
            description: this.state.description,
        };
        browser.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    }

    _startTick() {
        this._stopTick();
        this._tickHandle = browser.setInterval(() => {
            if (!this.state.running || !this.state.startTime) return;
            this.state.elapsed = Math.floor(
                (Date.now() - new Date(this.state.startTime).getTime()) / 1000
            );
        }, 1000);
    }

    _stopTick() {
        if (this._tickHandle) {
            browser.clearInterval(this._tickHandle);
            this._tickHandle = null;
        }
    }

    formatElapsed() {
        const s = this.state.elapsed;
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        const sec = s % 60;
        return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    }

    onClickStart() {
        const desc = window.prompt("What are you working on?", "") || "";
        this.state.running = true;
        this.state.startTime = new Date().toISOString();
        this.state.description = desc;
        this.state.elapsed = 0;
        this._persist();
        this._startTick();
    }

    async onClickStop() {
        this._stopTick();
        const stopTime = new Date().toISOString();
        const startTime = this.state.startTime;
        const description = this.state.description;

        try {
            const result = await this.orm.call("kob.timer.entry", "commit_entry", [{
                description,
                start_time: startTime.replace("T", " ").slice(0, 19),
                stop_time: stopTime.replace("T", " ").slice(0, 19),
            }]);
            const mins = Math.round(result.duration_seconds / 60);
            this.notification.add(
                `Timer stopped — ${mins} min logged`,
                { type: "success" },
            );
        } catch (e) {
            this.notification.add(
                "Failed to commit timer entry: " + (e.message || e),
                { type: "danger" },
            );
        } finally {
            this.state.running = false;
            this.state.startTime = null;
            this.state.description = "";
            this.state.elapsed = 0;
            browser.localStorage.removeItem(STORAGE_KEY);
        }
    }
}

registry
    .category("systray")
    .add("kob_timesheet_navbar.timer", {
        Component: KobTimesheetTimerButton,
    }, { sequence: 50 });
