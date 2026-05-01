import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { CompanySwitcher } from "@/components/CompanySwitcher";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";

const NAV: Array<{ to: string; key: string; group: "wms" | "ops" | "fin" | "core" }> = [
  { to: "/", key: "nav.home", group: "wms" },
  { to: "/products", key: "nav.products", group: "wms" },
  { to: "/warehouses", key: "nav.warehouses", group: "wms" },
  { to: "/transfers", key: "nav.transfers", group: "wms" },
  { to: "/outbound", key: "nav.outbound", group: "ops" },
  { to: "/couriers", key: "nav.couriers", group: "ops" },
  { to: "/counts", key: "nav.counts", group: "ops" },
  { to: "/quality", key: "nav.quality", group: "ops" },
  { to: "/ops", key: "nav.ops", group: "ops" },
  { to: "/purchase", key: "nav.purchase", group: "fin" },
  { to: "/manufacturing", key: "nav.manufacturing", group: "fin" },
  { to: "/sales", key: "nav.sales", group: "fin" },
  { to: "/accounting", key: "nav.accounting", group: "fin" },
  { to: "/hr", key: "nav.hr", group: "fin" },
  { to: "/audit", key: "nav.audit", group: "fin" },
  { to: "/users", key: "nav.users", group: "core" },
  { to: "/group", key: "nav.group", group: "core" },
];

const GROUP_TONE: Record<string, string> = {
  wms: "data-[active=true]:bg-sky-50 data-[active=true]:text-sky-700",
  ops: "data-[active=true]:bg-violet-50 data-[active=true]:text-violet-700",
  fin: "data-[active=true]:bg-emerald-50 data-[active=true]:text-emerald-700",
  core: "data-[active=true]:bg-slate-100 data-[active=true]:text-slate-900",
};

export default function Layout() {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] items-center gap-6 px-6 py-2.5">
          <div className="flex shrink-0 items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-md bg-brand-600 text-sm font-bold text-white">
              K
            </div>
            <span className="whitespace-nowrap text-base font-semibold text-slate-900">
              KOB-ERP
            </span>
          </div>

          <nav className="flex min-w-0 flex-1 items-center gap-0.5 overflow-x-auto">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) =>
                  cn(
                    "shrink-0 whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm transition",
                    isActive
                      ? GROUP_TONE[n.group] + ' bg-slate-100 text-slate-900 font-medium'
                      : "text-slate-600 hover:bg-slate-100",
                  )
                }
              >
                {t(n.key)}
              </NavLink>
            ))}
          </nav>

          <div className="flex shrink-0 items-center gap-2">
            <CompanySwitcher />
            <LanguageSwitcher />
            <span className="hidden whitespace-nowrap text-sm text-slate-600 lg:inline">
              {user?.full_name}
            </span>
            <button
              onClick={logout}
              className="whitespace-nowrap rounded-md border border-slate-300 px-3 py-1 text-xs text-slate-700 hover:bg-slate-50"
            >
              {t("action.signOut")}
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1400px] px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
