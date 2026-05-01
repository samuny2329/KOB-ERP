/** Page-level sheet wrapper — Odoo 19 control-panel feel.
 *
 * Wraps a record/list/form view with a consistent header (title + breadcrumb +
 * primary action area) and a white sheet container.  Mirrors Odoo's form-view
 * sheet: a white surface on the grey app background, with a slim control-panel
 * row above for the title + breadcrumb + buttons.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SheetProps {
  title: string;
  subtitle?: string;
  breadcrumb?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  /** Set to false if the children already render their own surface (e.g. a List) */
  framed?: boolean;
}

export function Sheet({
  title,
  subtitle,
  breadcrumb,
  actions,
  children,
  className,
  framed = false,
}: SheetProps) {
  return (
    <div className={cn("space-y-4", className)}>
      {/* Control panel — slim row with title left, actions right. */}
      <div className="flex flex-wrap items-end justify-between gap-3 border-b border-odoo-border pb-3">
        <div className="min-w-0">
          {breadcrumb && (
            <div className="mb-1 text-[11px] uppercase tracking-[0.12em] text-odoo-textMuted">
              {breadcrumb}
            </div>
          )}
          <h1 className="truncate text-[20px] font-semibold text-odoo-text">{title}</h1>
          {subtitle && (
            <p className="mt-0.5 text-[13px] text-odoo-textMuted">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
      </div>
      {framed ? <div className="kob-sheet">{children}</div> : children}
    </div>
  );
}
