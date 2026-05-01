/** Odoo 19-styled top bar for KOB-ERP.
 *
 * - 46px purple navbar (#714B67), white text, hover = darker overlay.
 * - Brand block on the left ("KOB-ERP") separated by a vertical divider.
 * - Active nav item gets an inset bottom underline (Odoo's accent).
 * - Right cluster: company switcher · language · user · sign-out.
 */

import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { CompanySwitcher } from "@/components/CompanySwitcher";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const NAV: Array<{ to: string; key: string }> = [
  { to: "/", key: "nav.home" },
  { to: "/products", key: "nav.products" },
  { to: "/warehouses", key: "nav.warehouses" },
  { to: "/transfers", key: "nav.transfers" },
  { to: "/outbound", key: "nav.outbound" },
  { to: "/couriers", key: "nav.couriers" },
  { to: "/counts", key: "nav.counts" },
  { to: "/quality", key: "nav.quality" },
  { to: "/ops", key: "nav.ops" },
  { to: "/purchase", key: "nav.purchase" },
  { to: "/manufacturing", key: "nav.manufacturing" },
  { to: "/sales", key: "nav.sales" },
  { to: "/accounting", key: "nav.accounting" },
  { to: "/hr", key: "nav.hr" },
  { to: "/audit", key: "nav.audit" },
  { to: "/users", key: "nav.users" },
  { to: "/group", key: "nav.group" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-odoo-appBg">
      <header className="sticky top-0 z-30 kob-navbar">
        <div className="mx-auto flex h-full w-full max-w-[1600px] items-stretch gap-1 px-3">
          <div className="kob-brand">
            <span className="kob-brand-mark">K</span>
            <span className="whitespace-nowrap text-[15px]">KOB-ERP</span>
          </div>

          <nav className="flex min-w-0 flex-1 items-stretch overflow-x-auto">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
              >
                {({ isActive }) => (
                  <span
                    className="kob-navbar-link whitespace-nowrap"
                    data-active={isActive ? "true" : "false"}
                  >
                    {t(n.key)}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="flex shrink-0 items-center gap-1.5 pl-2">
            <CompanySwitcher />
            <LanguageSwitcher />
            <span className="hidden whitespace-nowrap text-[13px] text-white/85 lg:inline">
              {user?.full_name}
            </span>
            <button
              onClick={logout}
              className="whitespace-nowrap rounded border border-white/30 px-2.5 py-1 text-[12px] text-white/95 hover:bg-black/20"
            >
              {t("action.signOut")}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1600px] px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
