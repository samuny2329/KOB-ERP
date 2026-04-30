import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StateBadge } from "@/components/StateBadge";

interface SalesOrder {
  id: number;
  number: string;
  customer_id: number;
  state: string;
  order_date: string;
  total_amount: number;
  currency: string;
}

interface Customer {
  id: number;
  code: string;
  name: string;
}

export default function SalesPage() {
  const { data: orders = [], isLoading } = useQuery<SalesOrder[]>({
    queryKey: ["sales-orders"],
    queryFn: () => api.get("/api/v1/sales/orders").then((r) => r.data),
  });

  const { data: customers = [] } = useQuery<Customer[]>({
    queryKey: ["customers"],
    queryFn: () => api.get("/api/v1/sales/customers").then((r) => r.data),
  });

  const customerMap = Object.fromEntries(customers.map((c) => [c.id, c.name]));

  const totalRevenue = orders
    .filter((o) => !["cancelled", "draft"].includes(o.state))
    .reduce((sum, o) => sum + o.total_amount, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Sales</h1>
          <p className="text-sm text-slate-500">{customers.length} customers · {orders.length} orders</p>
        </div>
        <div className="rounded-lg bg-teal-50 px-4 py-2 text-right">
          <div className="text-xs text-teal-600">Total Revenue</div>
          <div className="text-lg font-bold text-teal-700">
            ฿{totalRevenue.toLocaleString("th-TH", { minimumFractionDigits: 2 })}
          </div>
        </div>
      </div>

      {/* Customer grid */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Customers</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {customers.slice(0, 6).map((c) => (
            <div key={c.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="font-medium text-slate-900">{c.name}</div>
              <div className="text-xs text-slate-400">{c.code}</div>
            </div>
          ))}
          {customers.length === 0 && <p className="text-sm text-slate-400">No customers yet.</p>}
        </div>
      </section>

      {/* Orders */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Sales Orders</h2>
        {isLoading ? (
          <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-12 animate-pulse rounded bg-slate-100" />)}</div>
        ) : orders.length === 0 ? (
          <p className="text-slate-400 text-sm">No sales orders yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Number</th>
                  <th className="px-4 py-2 text-left">Customer</th>
                  <th className="px-4 py-2 text-left">Date</th>
                  <th className="px-4 py-2 text-right">Total</th>
                  <th className="px-4 py-2 text-left">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs">{o.number}</td>
                    <td className="px-4 py-3">{customerMap[o.customer_id] ?? "—"}</td>
                    <td className="px-4 py-3 text-slate-500">{o.order_date}</td>
                    <td className="px-4 py-3 text-right font-medium">
                      {o.total_amount.toLocaleString("th-TH", { style: "currency", currency: o.currency })}
                    </td>
                    <td className="px-4 py-3"><StateBadge state={o.state} /></td>
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
