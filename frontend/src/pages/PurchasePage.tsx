import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StateBadge } from "@/components/StateBadge";

interface PurchaseOrder {
  id: number;
  number: string;
  vendor_id: number;
  state: string;
  order_date: string;
  total_amount: number;
  currency: string;
}

interface Vendor {
  id: number;
  code: string;
  name: string;
}

export default function PurchasePage() {
  const { data: orders = [], isLoading: ordersLoading } = useQuery<PurchaseOrder[]>({
    queryKey: ["purchase-orders"],
    queryFn: () => api.get("/api/v1/purchase/orders").then((r) => r.data),
  });

  const { data: vendors = [] } = useQuery<Vendor[]>({
    queryKey: ["vendors"],
    queryFn: () => api.get("/api/v1/purchase/vendors").then((r) => r.data),
  });

  const vendorMap = Object.fromEntries(vendors.map((v) => [v.id, v.name]));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Purchase Orders</h1>
        <p className="text-sm text-slate-500">{vendors.length} vendors · {orders.length} orders</p>
      </div>

      {/* Vendors */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Vendors</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {vendors.slice(0, 6).map((v) => (
            <div key={v.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="font-medium text-slate-900">{v.name}</div>
              <div className="text-xs text-slate-400">{v.code}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Orders table */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Orders</h2>
        {ordersLoading ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded bg-slate-100" />
            ))}
          </div>
        ) : orders.length === 0 ? (
          <p className="text-slate-400 text-sm">No purchase orders yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Number</th>
                  <th className="px-4 py-2 text-left">Vendor</th>
                  <th className="px-4 py-2 text-left">Date</th>
                  <th className="px-4 py-2 text-right">Total</th>
                  <th className="px-4 py-2 text-left">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs">{o.number}</td>
                    <td className="px-4 py-3">{vendorMap[o.vendor_id] ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-500">{o.order_date}</td>
                    <td className="px-4 py-3 text-right font-medium">
                      {o.total_amount.toLocaleString("th-TH", { style: "currency", currency: o.currency })}
                    </td>
                    <td className="px-4 py-3">
                      <StateBadge state={o.state} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
