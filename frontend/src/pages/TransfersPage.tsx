import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { inventoryApi } from "@/lib/wms";
import { StateBadge } from "@/components/StateBadge";

const NEXT_ACTION: Record<string, "confirm" | "done" | null> = {
  draft: "confirm",
  confirmed: "done",
  done: null,
  cancelled: null,
};

export default function TransfersPage() {
  const qc = useQueryClient();
  const transfers = useQuery({
    queryKey: ["transfers"],
    queryFn: () => inventoryApi.transfers({ limit: 50 }),
  });

  const advance = useMutation({
    mutationFn: async ({ id, action }: { id: number; action: "confirm" | "done" | "cancel" }) => {
      if (action === "confirm") return inventoryApi.confirmTransfer(id);
      if (action === "done") return inventoryApi.doneTransfer(id);
      return inventoryApi.cancelTransfer(id);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["transfers"] }),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Transfers</h1>
      <p className="mt-1 text-sm text-slate-500">
        Inbound, outbound, and internal movements.  draft → confirmed → done.
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-2.5">Reference</th>
              <th className="px-4 py-2.5">State</th>
              <th className="px-4 py-2.5">Lines</th>
              <th className="px-4 py-2.5">Origin</th>
              <th className="px-4 py-2.5">Scheduled</th>
              <th className="px-4 py-2.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {transfers.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {transfers.data?.length === 0 && !transfers.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  No transfers yet
                </td>
              </tr>
            )}
            {transfers.data?.map((t) => {
              const next = NEXT_ACTION[t.state];
              return (
                <tr key={t.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-mono text-xs">{t.name}</td>
                  <td className="px-4 py-2.5">
                    <StateBadge state={t.state} />
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">{t.lines.length}</td>
                  <td className="px-4 py-2.5 text-slate-600">{t.origin ?? "—"}</td>
                  <td className="px-4 py-2.5 text-slate-600">
                    {t.scheduled_date
                      ? new Date(t.scheduled_date).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {next && (
                      <button
                        onClick={() => advance.mutate({ id: t.id, action: next })}
                        disabled={advance.isPending}
                        className="rounded-md bg-brand-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-700 disabled:opacity-50"
                      >
                        {next === "confirm" ? "Confirm" : "Validate"}
                      </button>
                    )}
                    {(t.state === "draft" || t.state === "confirmed") && (
                      <button
                        onClick={() => advance.mutate({ id: t.id, action: "cancel" })}
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
