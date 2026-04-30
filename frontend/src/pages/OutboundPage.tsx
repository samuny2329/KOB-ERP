import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { outboundApi, type OutboundOrderState } from "@/lib/wms";
import { StateBadge } from "@/components/StateBadge";

const NEXT: Record<OutboundOrderState, OutboundOrderState | null> = {
  pending: "picking",
  picking: "picked",
  picked: "packing",
  packing: "packed",
  packed: "shipped",
  shipped: null,
  cancelled: null,
};

const ACTION_LABEL: Record<OutboundOrderState, string> = {
  picking: "Start picking",
  picked: "Mark picked",
  packing: "Start packing",
  packed: "Mark packed",
  shipped: "Mark shipped",
  pending: "",
  cancelled: "",
};

export default function OutboundPage() {
  const qc = useQueryClient();
  const orders = useQuery({
    queryKey: ["outbound-orders"],
    queryFn: () => outboundApi.orders({ limit: 50 }),
  });

  const advance = useMutation({
    mutationFn: ({ id, target }: { id: number; target: OutboundOrderState }) =>
      outboundApi.transitionOrder(id, target),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["outbound-orders"] }),
  });

  return (
    <div>
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Outbound orders</h1>
          <p className="mt-1 text-sm text-slate-500">
            pending → picking → picked → packing → packed → shipped
          </p>
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-2.5">Reference</th>
              <th className="px-4 py-2.5">Customer</th>
              <th className="px-4 py-2.5">Platform</th>
              <th className="px-4 py-2.5">State</th>
              <th className="px-4 py-2.5">Lines</th>
              <th className="px-4 py-2.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {orders.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {orders.data?.length === 0 && !orders.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  No outbound orders yet
                </td>
              </tr>
            )}
            {orders.data?.map((o) => {
              const next = NEXT[o.state];
              return (
                <tr key={o.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-mono text-xs">{o.ref}</td>
                  <td className="px-4 py-2.5">{o.customer_name}</td>
                  <td className="px-4 py-2.5 text-slate-600 capitalize">{o.platform}</td>
                  <td className="px-4 py-2.5">
                    <StateBadge state={o.state} />
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">{o.lines.length}</td>
                  <td className="px-4 py-2.5 text-right">
                    {next && (
                      <button
                        onClick={() => advance.mutate({ id: o.id, target: next })}
                        disabled={advance.isPending}
                        className="rounded-md bg-fuchsia-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-fuchsia-700 disabled:opacity-50"
                      >
                        {ACTION_LABEL[next]}
                      </button>
                    )}
                    {(o.state !== "shipped" && o.state !== "cancelled") && (
                      <button
                        onClick={() => advance.mutate({ id: o.id, target: "cancelled" })}
                        disabled={advance.isPending}
                        className="ml-2 rounded-md border border-slate-300 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
