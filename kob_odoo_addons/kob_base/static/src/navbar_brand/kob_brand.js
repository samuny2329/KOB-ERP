/** @odoo-module **/

/**
 * KOB ERP — guarantee a working `< AppName | submenu items` navbar.
 *
 * Strategy:
 *   1. **Service that auto-syncs currentMenu**.  After every
 *      ACTION_MANAGER:UI-UPDATED event we check whether
 *      ``menuService.getCurrentApp()`` is set.  If not (typical post-
 *      reload state — closure ``currentAppId`` is unset) we walk the
 *      menu cache, find the menu owning the running action, and call
 *      ``menuService.setCurrentMenu(menu)``.  This restores the
 *      native Odoo navbar render (brand + sections) without any
 *      template patching.
 *
 *   2. **Welcome page brand suppression**.  On the welcome client
 *      action we want NO brand and NO submenu (the user is already
 *      home).  We hide them via CSS scoped to the welcome action.
 *
 *   3. **Brand-as-back-button**.  Capture-phase click delegate on
 *      ``.o_menu_brand``: any click on it routes to /odoo (welcome).
 *
 *   4. **DOM-injection fallback**.  If for some reason setCurrentMenu
 *      didn't set an app (e.g. action not owned by any menu the user
 *      has access to), inject a minimal "KOB ERP" anchor so the user
 *      always has a back-button.
 */

import { registry } from "@web/core/registry";

const WELCOME_TAG = "kob_base.welcome";
const FALLBACK_CLASS = "kob_fallback_brand";

console.log("[KobBrand] auto-sync + back-button bootstrap loaded");

// ── 1. Service: auto-sync currentMenu after every action change ──
//
// On a hard refresh, ``menuService``'s closure ``currentAppId`` is
// reset.  The NavBar's brand template only renders when ``currentApp``
// is truthy, so without this we'd land on a module page with no
// brand.  Each action change → walk the menu cache for one that owns
// the running action → ``setCurrentMenu`` → MENUS:APP-CHANGED →
// NavBar re-renders brand + sections natively.
const kobAutoCurrentMenuService = {
    dependencies: ["action", "menu"],
    start(env, { action, menu }) {
        const sync = () => {
            try {
                if (menu.getCurrentApp()) {
                    return;
                }
                const ctrl = action.currentController;
                const actionId = ctrl && ctrl.action && ctrl.action.id;
                if (!actionId || !menu.getAll) {
                    return;
                }
                const all = menu.getAll();
                const owning = all.find(
                    (m) => m && m.actionID === actionId,
                );
                if (owning) {
                    menu.setCurrentMenu(owning);
                }
            } catch (e) {
                console.warn("[KobBrand] auto-sync failed", e);
            }
        };
        env.bus.addEventListener("ACTION_MANAGER:UI-UPDATED", sync);
        // First-load case: sync immediately too.
        Promise.resolve().then(sync);
    },
};
registry
    .category("services")
    .add("kob_auto_current_menu", kobAutoCurrentMenuService);

// ── 2. Brand-as-back-button + DOM fallback (capture-phase click) ──

function ensureFallbackBrand(navbar) {
    if (!navbar) return;

    const realBrand = navbar.querySelector(
        ".o_menu_brand:not(." + FALLBACK_CLASS + ")",
    );
    if (realBrand) {
        // OWL rendered a real app brand.  Remove any stale fallback so
        // we don't end up with TWO back-buttons in the navbar.
        navbar
            .querySelectorAll("." + FALLBACK_CLASS)
            .forEach((el) => el.remove());
        // Mark it so kob_brand.scss can prepend the animated chevron.
        realBrand.classList.add("kob-real-brand");
        return;
    }

    if (navbar.querySelector("." + FALLBACK_CLASS)) {
        return;
    }
    const a = document.createElement("a");
    a.className = "o_menu_brand d-flex align-items-center " + FALLBACK_CLASS;
    a.href = "/odoo";
    a.textContent = "KOB ERP";
    a.style.cssText = (
        "color: inherit; font-weight: 600; padding: 0 0.75rem; "
        + "text-decoration: none; cursor: pointer;"
    );
    a.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        window.location.assign("/odoo");
    });
    const breadcrumbs = navbar.querySelector(".o_navbar_breadcrumbs");
    const appsMenu = navbar.querySelector(".o_navbar_apps_menu");
    if (breadcrumbs) {
        navbar.insertBefore(a, breadcrumbs);
    } else if (appsMenu && appsMenu.nextSibling) {
        navbar.insertBefore(a, appsMenu.nextSibling);
    } else {
        navbar.prepend(a);
    }
}

function pass() {
    // Backend asset bundles can load before <body> is parsed, so guard.
    if (!document.body) {
        return;
    }
    const navbars = document.querySelectorAll(".o_main_navbar");
    navbars.forEach(ensureFallbackBrand);
}

// Capture-phase click on ANY .o_menu_brand → go home.
document.addEventListener(
    "click",
    (ev) => {
        const target = ev.target.closest(".o_menu_brand, .o_menu_toggle");
        if (!target) return;
        if (!document.body.contains(target)) return;
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
        window.location.assign("/odoo");
    },
    true,
);

// Watch the body for navbar mounts and run our fallback pass.
function bootstrapObserver() {
    const target = document.body;
    if (!target) {
        // <body> not parsed yet — try again after the next event loop.
        setTimeout(bootstrapObserver, 50);
        return;
    }
    new MutationObserver(pass).observe(target, {
        childList: true,
        subtree: true,
    });
    pass();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrapObserver);
} else {
    bootstrapObserver();
}
// Belt-and-braces — re-run after typical OWL mount latencies.
setTimeout(pass, 100);
setTimeout(pass, 500);
setTimeout(pass, 1500);
