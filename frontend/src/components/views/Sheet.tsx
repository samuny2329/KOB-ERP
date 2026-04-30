/** Page-level sheet wrapper.
 *
 * Wraps a record/list/form view with a consistent header (title + breadcrumb +
 * primary action area) and a content frame.  Keeps every module visually
 * consistent without each page re-implementing the same scaffolding.
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
}

export function Sheet({ title, subtitle, breadcrumb, actions, children, className }: SheetProps) {
  return (
    <div className={cn("space-y-5", className)}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          {breadcrumb && (
            <div className="mb-1 text-xs text-slate-500">{breadcrumb}</div>
          )}
          <h1 className="truncate text-2xl font-semibold text-slate-900">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  );
}
