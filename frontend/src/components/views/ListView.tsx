/** Generic record-list table.
 *
 * Each column is a `{ key, header, render }` triple — the render function is
 * passed the row and returns a React node, keeping cell formatting at the
 * call site instead of forcing the table to know every domain shape.
 */

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

export interface Column<Row> {
  key: string;
  header: string;
  className?: string; // applied to <td> + <th>
  render: (row: Row) => ReactNode;
}

interface ListViewProps<Row> {
  rows: Row[];
  columns: Column<Row>[];
  loading?: boolean;
  emptyHint?: string;
  rowKey: (row: Row) => string | number;
  onRowClick?: (row: Row) => void;
}

export function ListView<Row>({
  rows,
  columns,
  loading = false,
  emptyHint,
  rowKey,
  onRowClick,
}: ListViewProps<Row>) {
  const { t } = useTranslation();
  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-slate-200">
        <thead className="bg-slate-50/80 text-left text-[11px] font-medium uppercase tracking-wider text-slate-500">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={cn("px-4 py-2.5", c.className)}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 text-sm">
          {loading && (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-slate-400"
              >
                {t("status.loading")}
              </td>
            </tr>
          )}
          {!loading && rows.length === 0 && (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-10 text-center text-sm text-slate-400"
              >
                {emptyHint ?? t("status.empty")}
              </td>
            </tr>
          )}
          {!loading &&
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                className={cn(
                  "transition",
                  onRowClick ? "cursor-pointer hover:bg-slate-50" : null,
                )}
                onClick={() => onRowClick?.(row)}
              >
                {columns.map((c) => (
                  <td key={c.key} className={cn("px-4 py-2.5 align-middle", c.className)}>
                    {c.render(row)}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
