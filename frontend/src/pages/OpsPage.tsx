import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StateBadge } from "@/components/StateBadge";

interface PlatformOrder {
  id: number;
  platform: string;
  external_order_id: string;
  status: string;
  buyer_name: string | null;
  total_amount: number;
  currency: string;
  ordered_at: string | null;
}

interface KpiAlert {
  id: number;
  metric_name: string;
  severity: string;
  message: string;
  actual_value: number | null;
  target_value: number | null;
  resolved: boolean;
  created_at: string;
}

interface DailyReport {
  id: number;
  report_date: string;
  warehouse_id: number;
  orders_received: number;
  orders_shipped: number;
  total_revenue: number;
}

const PLATFORM_COLORS: Record<string, string> = {
  shopee: "bg-orange-100 text-orange-700",
  lazada: "bg-blue-100 text-blue-700",
  tiktok: "bg-slate-900 text-white",
  manual: "bg-slate-100 text-slate-600",
};

const SEVERITY_COLORS: Record<string, string> = {
  info: "bg-blue-100 text-blue-700",
  warning: "bg-amber-100 text-amber-700",
  critical: "bg-red-100 text-red-700",
};

export default function OpsPage() {
  const { data: orders = [], isLoading: ordersLoading } = useQuery<PlatformOrder[]>({
    queryKey: ["platform-orders"],
    queryFn: () => api.get("/api/v1/ops/platform-orders").then((r) => r.data),
  });

  const { data: alerts = [] } = useQuery<KpiAlert[]>({
    queryKey: ["kpi-alerts"],
    queryFn: () => api.get("/api/v1/ops/kpi/alerts").then((r) => r.data),
  });

  const { data: reports = [] } = useQuery<DailyReport[]>({
    queryKey: ["daily-reports"],
    queryFn: () => api.get("/api/v1/ops/reports/daily").then((r) => r.data),
  });

  const byPlatform = orders.reduce<Record<string, number>>((acc, o) => {
    acc[o.platform] = (acc[o.platform] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Operations & KPI</h1>
        <p className="text-sm text-slate-500">
          {orders.length} platform orders · {alerts.length} active alerts
        </p>
      </div>

      {/* Platform breakdown */}
      <div className="flex gap-3 flex-wrap">
        {Object.entries(byPlatform).map(([p, count]) => (
          <div key={p} className={`rounded-lg px-4 py-2 flex items-center gap-2 ${PLATFORM_COLORS[p] ?? "bg-slate-100 text-slate-600"}`}>
            <span className="font-semibold capitalize">{p}</span>
            <span className="font-bold">{count}</span>
          </div>
        ))}
      </div>

      {/* KPI Alerts */}
      {alerts.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Active KPI Alerts</h2>
          <div className="space-y-2">
            {alerts.map((a) => (
              <div key={a.id} className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white p-3">
                <span className={`mt-0.5 rounded-full px-2 py-0.5 text-xs font-semibold ${SEVERITY_COLORS[a.severity] ?? "bg-slate-100"}`}>
                  {a.severity}
                </span>
                <div>
                  <div className="font-medium text-slate-900">{a.metric_name}</div>
                  <div className="text-sm text-slate-500">{a.message}</div>
                  {a.actual_value !== null && (
                    <div className="text-xs text-slate-400">
                      Actual: {a.actual_value} / Target: {a.target_value}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Platform orders */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Platform Orders</h2>
        {ordersLoading ? (
          <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-12 animate-pulse rounded bg-slate-100" />)}</div>
        ) : orders.length === 0 ? (
          <p className="text-slate-400 text-sm">No platform orders yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Order ID</th>
                  <th className="px-4 py-2 text-left">Platform</th>
                  <th className="px-4 py-2 text-left">Buyer</th>
                  <th className="px-4 py-2 text-right">Amount</th>
                  <th className="px-4 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs">{o.external_order_id}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${PLATFORM_COLORS[o.platform] ?? "bg-slate-100"}`}>
                        {o.platform}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{o.buyer_name ?? "—"}</td>
                    <td className="px-4 py-3 text-right font-medium">
                      {o.total_amount.toLocaleString("th-TH", { style: "currency", currency: o.currency })}
                    </td>
                    <td className="px-4 py-3"><StateBadge state={o.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Daily reports */}
      {reports.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Daily Reports</h2>
          <div className="grid gap-3 sm:grid-cols-3">
            {reports.slice(0, 6).map((r) => (
              <div key={r.id} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="font-medium text-slate-900">{r.report_date}</div>
                <div className="mt-2 grid grid-cols-2 gap-1 text-xs text-slate-500">
                  <span>Received: <b className="text-slate-800">{r.orders_received}</b></span>
                  <span>Shipped: <b className="text-slate-800">{r.orders_shipped}</b></span>
                  <span className="col-span-2">Revenue: <b className="text-teal-700">฿{r.total_revenue.toLocaleString()}</b></span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
