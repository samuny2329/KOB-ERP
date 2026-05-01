/** @odoo-module **/

/**
 * KOB ERP — make the navbar brand mark behave as a "back to Welcome" button.
 *
 * We intentionally avoid an XML template patch (which breaks the webclient
 * mount in Odoo 19 when the xpath shape changes between versions).  Instead
 * we patch NavBar's setup to attach a capture-phase click listener on
 * `.o_menu_brand` that always returns the user to the Welcome dashboard.
 *
 * Visually, kob_theme already paints the K mark + KOB ERP wordmark; this
 * file just owns the behaviour.
 */

import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";

let _delegated = false;

patch(NavBar.prototype, {
    setup() {
        super.setup();
        if (_delegated) return;
        _delegated = true;

        const goWelcome = (ev) => {
            // Treat both the desktop brand (.o_menu_brand) and the
            // mobile/tablet burger toggle (.o_menu_toggle) as "go home".
            const target = ev.target.closest(".o_menu_brand, .o_menu_toggle");
            if (!target) return;
            if (!document.body.contains(target)) return;
            // Kill the event for everyone — including the DropdownItem's
            // onSelected handler attached to this same element.
            ev.preventDefault();
            ev.stopPropagation();
            ev.stopImmediatePropagation();
            // Hard reload to the welcome action.  We resolve its numeric
            // id via the action service (synchronously through cache) and
            // navigate to /odoo/action-<id> — bypasses Odoo's "last
            // visited action" router which would otherwise send us back
            // to whatever the user was looking at last.
            const action = this.actionService;
            (async () => {
                try {
                    const a = await action.loadAction(
                        "kob_base.action_kob_welcome",
                    );
                    window.location.assign(`/odoo/action-${a.id}`);
                } catch (e) {
                    console.warn("[KobBrand] welcome action not found", e);
                    window.location.assign("/odoo");
                }
            })();
        };

        // Capture phase so we win over Odoo's own DropdownItem onSelected.
        document.addEventListener("click", goWelcome, true);
    },
});
