import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { qualityApi } from "@/lib/wms";
import { StateBadge } from "@/components/StateBadge";
import { cn } from "@/lib/utils";

const SEVERITY_TONE: Record<string, string> = {
  minor: "bg-amber-100 text-amber-800",
  major: "bg-orange-100 text-orange-800",
  critical: "bg-rose-100 text-rose-800",
};

export default function QualityPage() {
  const qc = useQueryClient();
  const checks = useQuery({ queryKey: ["quality-checks"], queryFn: () => qualityApi.checks() });

  const transition = useMutation({
    mutationFn: ({ id, target }: { id: number; target: "passed" | "failed" | "skipped" }) =>
      qualityApi.transitionCheck(id, target),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quality-checks"] }),
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Quality checks</h1>
      <p className="mt-1 text-sm text-slate-500">
        Outgoing inspection.  Pending checks must be resolved before an order can ship.
      </p>

      <div className="mt-6 grid gap-4">
        {checks.isLoading && (
          <div className="rounded-xl border border-dashed border-slate-300 px-6 py-8 text-center text-sm text-slate-400">
            Loading…
          </div>
        )}
        {checks.data?.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 px-6 py-8 text-center text-sm text-slate-400">
            No quality checks yet
          </div>
        )}
        {checks.data?.map((c) => (
          <div
            key={c.id}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="font-mono text-xs text-slate-500">
                  Order #{c.order_id} · Product #{c.product_id}
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <StateBadge state={c.state} />
                  <span className="text-xs text-slate-500">
                    expected {c.expected_qty}
                  </span>
                </div>
                {c.check_notes && (
                  <p className="mt-2 text-sm text-slate-600">{c.check_notes}</p>
                )}
              </div>
              {c.state === "pending" && (
                <div className="flex gap-2">
                  <button
                    onClick={() => transition.mutate({ id: c.id, target: "passed" })}
                    className="rounded-md bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-700"
                  >
                    Pass
                  </button>
                  <button
                    onClick={() => transition.mutate({ id: c.id, target: "failed" })}
                    className="rounded-md bg-rose-600 px-3 py-1 text-xs font-medium text-white hover:bg-rose-700"
                  >
                    Fail
                  </button>
                  <button
                    onClick={() => transition.mutate({ id: c.id, target: "skipped" })}
                    className="rounded-md border border-slate-300 px-3 py-1 text-xs text-slate-700 hover:bg-slate-50"
                  >
                    Skip
                  </button>
                </div>
              )}
            </div>
            {c.defects.length > 0 && (
              <div className="mt-3 rounded-lg bg-rose-50 p-3">
                <div className="text-xs font-medium uppercase tracking-wider text-rose-700">
                  Defects
                </div>
                <ul className="mt-2 space-y-1">
                  {c.defects.map((d) => (
                    <li key={d.id} className="flex items-center gap-2 text-sm">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium uppercase",
                          SEVERITY_TONE[d.severity] ?? "bg-slate-100 text-slate-700",
                        )}
                      >
                        {d.severity}
                      </span>
                      <span className="font-medium text-slate-900">{d.defect_type}</span>
                      {d.description && (
                        <span className="text-slate-600">— {d.description}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
