/** @odoo-module **/

/**
 * KOB ERP — guarantee a clickable "KOB ERP" brand on every backend page.
 *
 * Why DOM injection instead of OWL patching:
 *   The original NavBar template only renders the `.o_menu_brand`
 *   DropdownItem when ``currentApp`` is truthy:
 *
 *       <DropdownItem t-if="!env.isSmall and currentApp" .../>
 *
 *   ``currentApp`` is computed from a closure variable in
 *   ``menuService`` (``currentAppId``) that is NEVER persisted.  On
 *   page reload (direct URL like /odoo/action-NN, or any non-menu
 *   navigation) it stays unset and the brand vanishes — taking the
 *   "back to Welcome" button with it.
 *
 *   We tried ``patch(NavBar.prototype, { get currentApp() {...} })`` —
 *   it works in some browser/cache states but observed to be ignored in
 *   others (Odoo 19 patch utility's super-via-getter chain has edge
 *   cases).  The robust fix is to bypass OWL entirely: a
 *   MutationObserver watches every navbar mount and injects a fallback
 *   brand whenever the real one is absent.
 */

// Path Odoo uses for the welcome action — used in the "we're on welcome"
// short-circuit to suppress the fallback brand.
const WELCOME_ACTION_PATTERN = "kob_base.welcome";
const FALLBACK_CLASS = "kob_fallback_brand";

console.log("[KobBrand] DOM-injection brand bootstrap loaded");

/** True if the user is currently on the Welcome client action. */
function isOnWelcome() {
    // Match via URL — we route to it as /odoo/action-<id>, but the
    // action *path* in the location may also be 'kob_base.welcome'.
    try {
        const path = window.location.pathname || "";
        if (path.includes(WELCOME_ACTION_PATTERN)) {
            return true;
        }
        // Heuristic: the welcome page has the .kob-welcome-root element
        // (defined in the XML template).
        if (document.querySelector(".kob-welcome-root, [data-kob-welcome]")) {
            return true;
        }
    } catch (_e) {
        /* ignore */
    }
    return false;
}

/** Inject the fallback brand into a navbar element if it doesn't already
 *  have a real or fallback brand. */
function ensureBrand(navbar) {
    if (!navbar) return;
    if (isOnWelcome()) {
        // Welcome page — remove any leftover fallback brand so the
        // home screen stays clean.
        const existing = navbar.querySelector("." + FALLBACK_CLASS);
        if (existing) existing.remove();
        return;
    }
    // Already has a real brand or our fallback? Nothing to do.
    if (navbar.querySelector(".o_menu_brand:not(." + FALLBACK_CLASS + ")")) {
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
    // Insert AFTER the apps-menu button, BEFORE the breadcrumbs slot.
    const appsMenu = navbar.querySelector(".o_navbar_apps_menu");
    const breadcrumbs = navbar.querySelector(".o_navbar_breadcrumbs");
    if (breadcrumbs) {
        navbar.insertBefore(a, breadcrumbs);
    } else if (appsMenu && appsMenu.nextSibling) {
        navbar.insertBefore(a, appsMenu.nextSibling);
    } else {
        navbar.prepend(a);
    }
}

/** Run ensureBrand on every navbar in the document. */
function pass() {
    const navbars = document.querySelectorAll(".o_main_navbar");
    navbars.forEach(ensureBrand);
}

// Watch the entire body for any DOM mutation — cheap operation, this
// only inserts when the navbar lacks a brand.
const observer = new MutationObserver(pass);
observer.observe(document.body || document.documentElement, {
    childList: true,
    subtree: true,
});
// Initial pass in case navbar is already mounted.
pass();
// And one more after the next tick to catch race-with-OWL-mount.
setTimeout(pass, 100);
setTimeout(pass, 500);
setTimeout(pass, 1500);
