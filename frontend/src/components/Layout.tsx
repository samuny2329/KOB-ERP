import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Home" },
  { to: "/products", label: "Products" },
  { to: "/warehouses", label: "Warehouses" },
  { to: "/transfers", label: "Transfers" },
  { to: "/outbound", label: "Outbound" },
  { to: "/couriers", label: "Couriers" },
  { to: "/counts", label: "Counts" },
  { to: "/quality", label: "Quality" },
  { to: "/audit", label: "Audit" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="grid h-7 w-7 place-items-center rounded-md bg-brand-600 text-sm font-bold text-white">
                K
              </div>
              <span className="text-base font-semibold text-slate-900">KOB-ERP</span>
            </div>
            <nav className="flex items-center gap-1">
              {NAV.map((n) => (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.to === "/"}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-3 py-1.5 text-sm",
                      isActive
                        ? "bg-brand-50 text-brand-700"
                        : "text-slate-600 hover:bg-slate-100",
                    )
                  }
                >
                  {n.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-600">{user?.full_name}</span>
            <button
              onClick={logout}
              className="rounded-md border border-slate-300 px-3 py-1 text-xs text-slate-700 hover:bg-slate-50"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
