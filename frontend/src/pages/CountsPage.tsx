import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { countsApi } from "@/lib/wms";
import { StateBadge } from "@/components/StateBadge";

const SESSION_NEXT: Record<string, string | null> = {
  draft: "in_progress",
  in_progress: "reconciling",
  reconciling: "done",
  done: null,
  cancelled: null,
};

export default function CountsPage() {
  const qc = useQueryClient();
  const sessions = useQuery({
    queryKey: ["count-sessions"],
    queryFn: () => countsApi.sessions(),
  });
  const advance = useMutation({
    mutationFn: ({ id, target }: { id: number; target: string }) =>
      countsApi.transitionSession(id, target),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["count-sessions"] }),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Cycle counts</h1>
      <p className="mt-1 text-sm text-slate-500">
        Session lifecycle: draft → in_progress → reconciling → done.  Tasks travel
        through assigned → counting → submitted → verified → approved.
      </p>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-2.5">Session</th>
              <th className="px-4 py-2.5">Type</th>
              <th className="px-4 py-2.5">State</th>
              <th className="px-4 py-2.5">Threshold</th>
              <th className="px-4 py-2.5">Period</th>
              <th className="px-4 py-2.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {sessions.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {sessions.data?.length === 0 && !sessions.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  No count sessions yet
                </td>
              </tr>
            )}
            {sessions.data?.map((s) => {
              const next = SESSION_NEXT[s.state];
              return (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5 font-mono text-xs">{s.name}</td>
                  <td className="px-4 py-2.5 capitalize text-slate-600">{s.session_type}</td>
                  <td className="px-4 py-2.5">
                    <StateBadge state={s.state} />
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">
                    {s.variance_threshold_pct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-2.5 text-slate-600">
                    {s.date_start ?? "—"} → {s.date_end ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    {next && (
                      <button
                        onClick={() => advance.mutate({ id: s.id, target: next })}
                        disabled={advance.isPending}
                        className="rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                      >
                        Move to {next}
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
