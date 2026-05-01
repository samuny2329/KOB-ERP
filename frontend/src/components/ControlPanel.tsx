/** Enterprise control panel — slim sticky bar atop every record/list view.
 *
 * Layout pattern shared by SAP Fiori (object page header), Odoo 19 (control
 * panel), and Salesforce Lightning (record-page header).  Slots:
 *   - Breadcrumb on the left (replaces the page title)
 *   - Primary actions (New, Save, Discard) immediately after crumbs
 *   - View switcher / pagination / search on the right
 *
 * Sits below the shellbar (also sticky), giving the classic two-tier header.
 */

import type { ReactNode } from "react";
import { Breadcrumb, type Crumb } from "@/components/Breadcrumb";
import { cn } from "@/lib/utils";

interface ControlPanelProps {
  crumbs: Crumb[];
  /** Buttons rendered immediately after the breadcrumb (e.g. New, Save). */
  actions?: ReactNode;
  /** Right-hand cluster (search, view switcher, pagination). */
  rightSlot?: ReactNode;
  className?: string;
}

export function ControlPanel({ crumbs, actions, rightSlot, className }: ControlPanelProps) {
  return (
    <div
      className={cn(
        "sticky top-[46px] z-20 -mx-6 flex flex-wrap items-center justify-between gap-3 border-b border-odoo-border bg-white px-6 py-2",
        className,
      )}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <Breadcrumb crumbs={crumbs} />
        {actions && <div className="flex items-center gap-1.5">{actions}</div>}
      </div>
      {rightSlot && <div className="flex items-center gap-2">{rightSlot}</div>}
    </div>
  );
}
