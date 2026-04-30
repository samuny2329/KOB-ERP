import { useMutation, useQuery } from "@tanstack/react-query";
import { outboundApi } from "@/lib/wms";
import { cn } from "@/lib/utils";

export default function ActivityLogPage() {
  const log = useQuery({
    queryKey: ["activity-log"],
    queryFn: () => outboundApi.activity({ limit: 200 }),
  });

  const verify = useMutation({ mutationFn: () => outboundApi.verifyChain() });

  return (
    <div>
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Activity log</h1>
          <p className="mt-1 text-sm text-slate-500">
            Tamper-evident SHA-256 hash-chain.  Each entry links to its predecessor.
          </p>
        </div>
        <button
          onClick={() => verify.mutate()}
          disabled={verify.isPending}
          className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-50"
        >
          {verify.isPending ? "Verifying…" : "Verify chain"}
        </button>
      </div>

      {verify.data && (
        <div
          className={cn(
            "mt-3 rounded-md px-3 py-2 text-sm",
            verify.data.valid
              ? "bg-emerald-50 text-emerald-800"
              : "bg-rose-50 text-rose-800",
          )}
        >
          {verify.data.valid
            ? "✓ Chain is intact — no tampering detected."
            : `✗ Chain broken at row ID ${verify.data.broken_at_id}.`}
        </div>
      )}

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-2.5">When</th>
              <th className="px-4 py-2.5">Actor</th>
              <th className="px-4 py-2.5">Action</th>
              <th className="px-4 py-2.5">Ref</th>
              <th className="px-4 py-2.5">Note</th>
              <th className="px-4 py-2.5">Hash</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {log.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {log.data?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                  No activity recorded yet
                </td>
              </tr>
            )}
            {log.data?.map((row) => (
              <tr key={row.id} className="hover:bg-slate-50">
                <td className="px-4 py-2 font-mono text-xs text-slate-600">
                  {new Date(row.occurred_at).toLocaleString()}
                </td>
                <td className="px-4 py-2 tabular-nums">
                  {row.actor_id ? `#${row.actor_id}` : "—"}
                </td>
                <td className="px-4 py-2">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px]">
                    {row.action}
                  </span>
                </td>
                <td className="px-4 py-2 font-mono text-xs">{row.ref ?? "—"}</td>
                <td className="px-4 py-2 text-slate-600">{row.note ?? "—"}</td>
                <td className="px-4 py-2 font-mono text-[10px] text-slate-400">
                  {row.block_hash.slice(0, 12)}…
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
