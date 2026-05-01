/** SAP Fiori-style shellbar for KOB-ERP.
 *
 *  ┌──────────────────────────────────────────────────────────────────┐
 *  │ K  KOB-ERP   ⊞ Apps  │  <current app context>  │  ⚙  🔔  user  ⏻ │  44px Belize navy
 *  └──────────────────────────────────────────────────────────────────┘
 *  Pages render their own ControlPanel beneath this.  No flat NavLink list
 *  — navigation happens through the Apps launcher overlay (⊞).
 */

import { useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { CompanySwitcher } from "@/components/CompanySwitcher";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { AppLauncher } from "@/components/AppLauncher";
import { MODULES } from "@/lib/modules";

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [appsOpen, setAppsOpen] = useState(false);

  // Map current pathname → active module (for the app-context display).
  const currentModule = useMemo(() => {
    const path = location.pathname.replace(/\/$/, "");
    return (
      MODULES.find((m) => m.route === path) ??
      MODULES.find((m) => path.startsWith(m.route + "/"))
    );
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-odoo-appBg">
      <header className="sticky top-0 z-30 kob-navbar">
        <div className="mx-auto flex h-full w-full max-w-[1600px] items-stretch gap-1 px-3">
          {/* Brand + Apps launcher */}
          <button
            type="button"
            onClick={() => navigate("/")}
            className="kob-brand transition hover:opacity-90"
            title="Home"
          >
            <span className="kob-brand-mark">K</span>
            <span className="whitespace-nowrap text-[15px]">KOB-ERP</span>
          </button>

          <button
            type="button"
            onClick={() => setAppsOpen(true)}
            className="kob-navbar-link inline-flex items-center gap-2 whitespace-nowrap"
            aria-label="Open apps launcher"
            title="Apps (Ctrl+K)"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden className="h-4 w-4">
              <path d="M3 3h4v4H3zM9 3h4v4H9zM15 3h2v4h-2zM3 9h4v4H3zM9 9h4v4H9zM15 9h2v4h-2zM3 15h4v2H3zM9 15h4v2H9zM15 15h2v2h-2z" />
            </svg>
            <span className="hidden sm:inline">Apps</span>
          </button>

          {/* Current-app context */}
          <div className="ml-2 hidden flex-1 items-center text-[13px] text-white/80 md:flex">
            {currentModule && (
              <span className="truncate">
                <span className="opacity-70">›</span> <span className="font-medium text-white">
                  {t(`nav.${currentModule.key}`, { defaultValue: currentModule.name })}
                </span>
              </span>
            )}
          </div>
          <div className="flex-1 md:hidden" />

          {/* Right cluster */}
          <div className="flex shrink-0 items-center gap-1.5 pl-2">
            <CompanySwitcher />
            <LanguageSwitcher />
            <span className="hidden whitespace-nowrap text-[13px] text-white/85 lg:inline">
              {user?.full_name}
            </span>
            <button
              onClick={logout}
              className="whitespace-nowrap rounded border border-white/30 px-2.5 py-1 text-[12px] text-white/95 hover:bg-black/20"
              title={t("action.signOut")}
            >
              ⏻
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1600px] px-6 py-6">
        <Outlet />
      </main>

      <AppLauncher open={appsOpen} onClose={() => setAppsOpen(false)} />
    </div>
  );
}
