/** @odoo-module **/

/**
 * KOB ERP — make the navbar brand mark behave as a "back to Welcome" button,
 * and hide the leftover module submenu while the user is on the Welcome page.
 *
 * We intentionally avoid an XML template patch (which breaks the webclient
 * mount in Odoo 19 when the xpath shape changes between versions).  Instead
 * we patch NavBar's setup to attach a capture-phase click listener on
 * `.o_menu_brand` that always returns the user to the Welcome dashboard,
 * and we override the `currentApp` getter so that — while the welcome
 * client action is the current controller — the navbar reports "no app",
 * which naturally hides every submenu the previous module rendered.
 *
 * Visually, kob_theme already paints the K mark + KOB ERP wordmark; this
 * file just owns the behaviour.
 *
 * Note on the menu service:
 *   `menuService.setCurrentMenu(undefined)` is a no-op in Odoo 19 — the
 *   service ignores falsy values:
 *
 *       function setCurrentMenu(menu) {
 *           menu = typeof menu === "number" ? _getMenu(menu) : menu;
 *           if (menu && menu.appID !== currentAppId) { ... }
 *       }
 *
 *   so currentAppId stays "stuck" on whichever module the user opened
 *   last.  The navbar reads `getCurrentApp()` to render the submenu and
 *   we cannot clear that closure.  Hence the getter override below —
 *   it short-circuits at the navbar level instead.
 */

import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";

const WELCOME_TAG = "kob_base.welcome";

let _delegated = false;

patch(NavBar.prototype, {
    /** Hide module submenus while the user sits on the Welcome page. */
    get currentApp() {
        try {
            const ctrl = this.actionService && this.actionService.currentController;
            const tag = ctrl && ctrl.action && ctrl.action.tag;
            if (tag === WELCOME_TAG) {
                return null;
            }
        } catch (_e) {
            /* fall through to default */
        }
        return super.currentApp;
    },

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
