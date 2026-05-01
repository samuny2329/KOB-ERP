/** @odoo-module **/

/**
 * KOB ERP — Home button on the navbar.
 *
 * Replaces the apps-menu dropdown that we hid in kob_theme.scss.  Always
 * visible at the far left of the systray; clicking it opens the Welcome
 * client action so users can flip back to the launcher from anywhere.
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class KobHomeButton extends Component {
    static template = "kob_base.HomeButton";
    static props = {};

    setup() {
        this.action = useService("action");
    }

    async onClick() {
        try {
            await this.action.doAction("kob_base.action_kob_welcome", {
                clearBreadcrumbs: true,
            });
        } catch (e) {
            console.warn("[KobHomeButton] welcome action not available", e);
        }
    }
}

// Pin the button to the LEFT of the systray (sequence -10000 = first).
registry.category("systray").add(
    "kob_base.HomeButton",
    { Component: KobHomeButton },
    { sequence: -10000 },
);
