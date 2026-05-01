/** Enterprise breadcrumb (SAP / Salesforce / Odoo all share this pattern).
 *
 * Horizontal stack of links with `›` separators.  Last crumb is the current
 * record/view (no link, slightly bolder).  Used in ControlPanel.
 */

import { Link } from "react-router-dom";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: ReactNode;
  to?: string;
}

interface BreadcrumbProps {
  crumbs: Crumb[];
  className?: string;
}

export function Breadcrumb({ crumbs, className }: BreadcrumbProps) {
  return (
    <nav
      aria-label="Breadcrumb"
      className={cn("flex items-center gap-1.5 text-[13px] text-odoo-textMuted", className)}
    >
      {crumbs.map((c, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={i} className="inline-flex items-center gap-1.5">
            {c.to && !isLast ? (
              <Link to={c.to} className="text-odoo-textMuted transition hover:text-brand-600">
                {c.label}
              </Link>
            ) : (
              <span className={cn(isLast ? "font-medium text-odoo-text" : "")}>{c.label}</span>
            )}
            {!isLast && <span className="text-odoo-textMuted">›</span>}
          </span>
        );
      })}
    </nav>
  );
}
