import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="grid h-8 w-8 place-items-center rounded-md bg-brand-600 font-bold text-white">
              K
            </div>
            <span className="text-lg font-semibold text-slate-900">KOB-ERP</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-600">{user?.full_name}</span>
            <button
              onClick={logout}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
        <h1 className="text-3xl font-semibold text-slate-900">Welcome back, {user?.full_name}</h1>
        <p className="mt-2 text-slate-600">
          Phase 1 — Core Engine. Modules will appear here as we ship them.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { name: "WMS", desc: "Warehouse + Inventory", phase: "Phase 2" },
            { name: "Purchase", desc: "PO + Vendor + Receipt", phase: "Phase 3" },
            { name: "Manufacturing", desc: "BoM + Subcon", phase: "Phase 3" },
            { name: "Sales", desc: "Quote + SO + Delivery", phase: "Phase 4" },
            { name: "Accounting", desc: "GL + AP/AR", phase: "Phase 5" },
            { name: "HR", desc: "Employee + Payroll", phase: "Phase 6" },
          ].map((m) => (
            <div
              key={m.name}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="text-xs font-medium uppercase tracking-wider text-brand-600">
                {m.phase}
              </div>
              <div className="mt-1 text-lg font-semibold text-slate-900">{m.name}</div>
              <div className="mt-1 text-sm text-slate-600">{m.desc}</div>
            </div>
          ))}
        </div>

        <section className="mt-10 rounded-xl border border-slate-200 bg-white p-6">
          <h2 className="text-lg font-semibold text-slate-900">Account</h2>
          <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-slate-500">Email</dt>
              <dd className="text-slate-900">{user?.email}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Role</dt>
              <dd className="text-slate-900">
                {user?.is_superuser ? "Superuser" : "User"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Last login</dt>
              <dd className="text-slate-900">
                {user?.last_login_at
                  ? new Date(user.last_login_at).toLocaleString()
                  : "—"}
              </dd>
            </div>
            <div>
              <dt className="text-slate-500">Member since</dt>
              <dd className="text-slate-900">
                {user?.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
              </dd>
            </div>
          </dl>
        </section>
      </main>
    </div>
  );
}
