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

        const goWelcome = async (ev) => {
            const brand = ev.target.closest(".o_menu_brand");
            if (!brand) return;
            if (!document.body.contains(brand)) return;
            ev.preventDefault();
            ev.stopPropagation();
            try {
                // 1. Open the Welcome dashboard.
                await this.actionService.doAction(
                    "kob_base.action_kob_welcome",
                    { clearBreadcrumbs: true },
                );
                // 2. Now clear the active app so the lingering Sales > …
                //    submenus disappear (the action above doesn't reset
                //    currentMenu by itself).
                if (this.menuService?.setCurrentMenu) {
                    this.menuService.setCurrentMenu(null);
                }
                // 3. Force the navbar to re-render so the submenu strip
                //    actually clears in the DOM.
                this.env?.bus?.trigger("MENUS:APP-CHANGED");
            } catch (e) {
                console.warn("[KobBrand] welcome action unavailable", e);
            }
        };

        // Capture phase so we win over Odoo's own DropdownItem onSelected.
        document.addEventListener("click", goWelcome, true);
    },
});
