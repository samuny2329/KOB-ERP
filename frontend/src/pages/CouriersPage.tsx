import { useQuery } from "@tanstack/react-query";
import { wmsApi, outboundApi } from "@/lib/wms";
import { StateBadge } from "@/components/StateBadge";

export default function CouriersPage() {
  const couriers = useQuery({ queryKey: ["couriers"], queryFn: wmsApi.couriers });
  const batches = useQuery({
    queryKey: ["dispatch-batches"],
    queryFn: () => outboundApi.dispatchBatches(),
  });

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-2xl font-semibold text-slate-900">Couriers</h1>
        <p className="mt-1 text-sm text-slate-500">
          Active carriers used for handover and tracking links.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {couriers.isLoading && (
            <div className="col-span-full rounded-xl border border-dashed border-slate-300 px-6 py-8 text-center text-sm text-slate-400">
              Loading…
            </div>
          )}
          {couriers.data?.length === 0 && (
            <div className="col-span-full rounded-xl border border-dashed border-slate-300 px-6 py-8 text-center text-sm text-slate-400">
              No couriers configured
            </div>
          )}
          {couriers.data?.map((c) => (
            <div
              key={c.id}
              className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
            >
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-3 w-3 rounded-full"
                  style={{ backgroundColor: c.color_hex ?? "#94a3b8" }}
                />
                <span className="font-mono text-xs text-slate-500">{c.code}</span>
              </div>
              <div className="mt-1 text-base font-semibold text-slate-900">{c.name}</div>
              {c.tracking_url_template && (
                <div className="mt-1 truncate text-xs text-slate-500">
                  {c.tracking_url_template}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold text-slate-900">Dispatch batches</h2>
        <p className="mt-1 text-sm text-slate-500">
          draft → scanning → dispatched.  One batch per courier per handover.
        </p>

        <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2.5">Batch</th>
                <th className="px-4 py-2.5">State</th>
                <th className="px-4 py-2.5">Courier</th>
                <th className="px-4 py-2.5">Scans</th>
                <th className="px-4 py-2.5">Dispatched at</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {batches.isLoading && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    Loading…
                  </td>
                </tr>
              )}
              {batches.data?.length === 0 && !batches.isLoading && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    No dispatch batches yet
                  </td>
                </tr>
              )}
              {batches.data?.map((b) => (
                <tr key={b.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-mono text-xs">{b.name}</td>
                  <td className="px-4 py-2.5">
                    <StateBadge state={b.state} />
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">#{b.courier_id}</td>
                  <td className="px-4 py-2.5 tabular-nums">{b.scans.length}</td>
                  <td className="px-4 py-2.5 text-slate-600">
                    {b.dispatched_at
                      ? new Date(b.dispatched_at).toLocaleString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
