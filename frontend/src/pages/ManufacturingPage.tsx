import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StateBadge } from "@/components/StateBadge";

interface Mo {
  id: number;
  number: string;
  product_id: number;
  qty_planned: number;
  qty_produced: number;
  state: string;
  scheduled_date: string | null;
}

interface Bom {
  id: number;
  code: string;
  name: string;
  product_id: number;
  output_qty: number;
  active: boolean;
}

export default function ManufacturingPage() {
  const { data: mos = [], isLoading } = useQuery<Mo[]>({
    queryKey: ["manufacturing-orders"],
    queryFn: () => api.get("/api/v1/mfg/orders").then((r) => r.data),
  });

  const { data: boms = [] } = useQuery<Bom[]>({
    queryKey: ["boms"],
    queryFn: () => api.get("/api/v1/mfg/boms").then((r) => r.data),
  });

  const stateCount = (s: string) => mos.filter((m) => m.state === s).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Manufacturing</h1>
        <p className="text-sm text-slate-500">{boms.length} BoMs · {mos.length} orders</p>
      </div>

      {/* KPI chips */}
      <div className="flex gap-3 flex-wrap">
        {["draft", "confirmed", "in_progress", "done"].map((s) => (
          <div key={s} className="rounded-lg border border-slate-200 bg-white px-4 py-2 flex items-center gap-2">
            <StateBadge state={s} />
            <span className="text-sm font-semibold">{stateCount(s)}</span>
          </div>
        ))}
      </div>

      {/* BoMs */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Bills of Materials</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {boms.map((b) => (
            <div key={b.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="font-medium text-slate-900">{b.name}</div>
              <div className="text-xs text-slate-400">{b.code} · qty {b.output_qty}</div>
            </div>
          ))}
          {boms.length === 0 && <p className="text-sm text-slate-400">No BoMs yet.</p>}
        </div>
      </section>

      {/* MOs table */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Manufacturing Orders</h2>
        {isLoading ? (
          <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-12 animate-pulse rounded bg-slate-100" />)}</div>
        ) : mos.length === 0 ? (
          <p className="text-slate-400 text-sm">No manufacturing orders yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Number</th>
                  <th className="px-4 py-2 text-left">Scheduled</th>
                  <th className="px-4 py-2 text-right">Planned</th>
                  <th className="px-4 py-2 text-right">Produced</th>
                  <th className="px-4 py-2 text-left">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {mos.map((m) => (
                  <tr key={m.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-xs">{m.number}</td>
                    <td className="px-4 py-3 text-slate-500">{m.scheduled_date ?? "—"}</td>
                    <td className="px-4 py-3 text-right">{m.qty_planned}</td>
                    <td className="px-4 py-3 text-right">{m.qty_produced}</td>
                    <td className="px-4 py-3"><StateBadge state={m.state} /></td>
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
