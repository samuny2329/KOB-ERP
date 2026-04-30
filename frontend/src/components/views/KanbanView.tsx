/** Card-grid view — same data as ListView, rendered as cards. */

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

interface KanbanViewProps<Row> {
  rows: Row[];
  loading?: boolean;
  emptyHint?: string;
  rowKey: (row: Row) => string | number;
  renderCard: (row: Row) => ReactNode;
  onCardClick?: (row: Row) => void;
}

export function KanbanView<Row>({
  rows,
  loading = false,
  emptyHint,
  rowKey,
  renderCard,
  onCardClick,
}: KanbanViewProps<Row>) {
  const { t } = useTranslation();
  if (loading) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-400">
        {t("status.loading")}
      </div>
    );
  }
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-sm text-slate-400">
        {emptyHint ?? t("status.empty")}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {rows.map((row) => (
        <button
          key={rowKey(row)}
          type="button"
          onClick={() => onCardClick?.(row)}
          className={cn(
            "rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition",
            "hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md",
            onCardClick ? "cursor-pointer" : "cursor-default",
          )}
        >
          {renderCard(row)}
        </button>
      ))}
    </div>
  );
}
