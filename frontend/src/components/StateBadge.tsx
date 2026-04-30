import { cn } from "@/lib/utils";

const COLORS: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  confirmed: "bg-amber-100 text-amber-800",
  done: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-rose-100 text-rose-800",
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
