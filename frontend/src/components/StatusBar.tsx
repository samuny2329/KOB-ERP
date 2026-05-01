/** Enterprise form workflow ribbon (SAP Fiori "object status" / Odoo
 * statusbar / Salesforce path) — shows every state in order with the
 * active one highlighted.
 *
 * Render a list of states; pass `current` for the currently active one.
 * If `onSelect` is given, states become clickable (use sparingly — only
 * for valid transitions).  Past states are dimmed; future states are
 * outlined.  The active state gets a purple pill.
 */

import { cn } from "@/lib/utils";

export interface StatusBarStep {
  value: string;
  label: string;
  /** If true, state is reachable from current via legal transition. */
  reachable?: boolean;
}

interface StatusBarProps {
  steps: StatusBarStep[];
  current: string;
  onSelect?: (value: string) => void;
  className?: string;
}

export function StatusBar({ steps, current, onSelect, className }: StatusBarProps) {
  const activeIdx = steps.findIndex((s) => s.value === current);

  return (
    <div
      role="status"
      aria-label="Workflow status"
      className={cn(
        "flex flex-wrap items-center gap-1 border-b border-odoo-border bg-white px-3 py-2",
        className,
      )}
    >
      {steps.map((s, i) => {
        const isActive = s.value === current;
        const isPast = i < activeIdx;
        const clickable = !!onSelect && s.reachable && !isActive;
        return (
          <button
            key={s.value}
            type="button"
            disabled={!clickable}
            onClick={() => clickable && onSelect?.(s.value)}
            className={cn(
              "rounded-full px-3 py-1 text-[12px] font-medium transition",
              isActive
                ? "bg-brand-500 text-white"
                : isPast
                ? "text-odoo-textMuted"
                : clickable
                ? "border border-odoo-border bg-white text-odoo-textMuted hover:border-brand-300 hover:text-brand-700"
                : "text-odoo-textMuted opacity-60",
            )}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
