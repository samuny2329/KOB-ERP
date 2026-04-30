import { cn } from "@/lib/utils";

const COLORS: Record<string, string> = {
  // Transfer
  draft: "bg-slate-100 text-slate-700",
  confirmed: "bg-amber-100 text-amber-800",
  done: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-rose-100 text-rose-800",
  // Outbound order
  pending: "bg-slate-100 text-slate-700",
  picking: "bg-sky-100 text-sky-800",
  picked: "bg-cyan-100 text-cyan-800",
  packing: "bg-violet-100 text-violet-800",
  packed: "bg-fuchsia-100 text-fuchsia-800",
  shipped: "bg-emerald-100 text-emerald-800",
  // Dispatch
  scanning: "bg-amber-100 text-amber-800",
  dispatched: "bg-emerald-100 text-emerald-800",
  // Cycle count
  in_progress: "bg-sky-100 text-sky-800",
  reconciling: "bg-violet-100 text-violet-800",
  assigned: "bg-slate-100 text-slate-700",
  counting: "bg-sky-100 text-sky-800",
  submitted: "bg-amber-100 text-amber-800",
  verified: "bg-cyan-100 text-cyan-800",
  approved: "bg-emerald-100 text-emerald-800",
  // Quality
  pending: "bg-slate-100 text-slate-700",
  passed: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
  skipped: "bg-slate-200 text-slate-600",
};

export function StateBadge({ state }: { state: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        COLORS[state] ?? "bg-slate-100 text-slate-700",
      )}
    >
      {state}
    </span>
  );
}
