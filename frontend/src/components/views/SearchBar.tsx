/** Odoo-style search bar — text input + filter chips + reset.
 *
 * Each chip is a key it controls: tap to toggle.  Multiple chips can be
 * active simultaneously; the parent reduces them into the query.
 */

import type { ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

export interface FilterChip {
  key: string;
  label: string;
}

interface SearchBarProps {
  value: string;
  onChange: (next: string) => void;
  filters?: FilterChip[];
  activeFilters?: Set<string>;
  onToggleFilter?: (key: string) => void;
  rightSlot?: React.ReactNode;
}

export function SearchBar({
  value,
  onChange,
  filters = [],
  activeFilters,
  onToggleFilter,
  rightSlot,
}: SearchBarProps) {
  const { t } = useTranslation();
  const handleInput = (e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative min-w-[14rem] flex-1">
        <input
          type="search"
          value={value}
          onChange={handleInput}
          placeholder={t("action.search")}
          className="block w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 pl-9 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
        <svg
          className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden
        >
          <path
            fillRule="evenodd"
            d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.45 4.39l3.08 3.08a.75.75 0 11-1.06 1.06l-3.08-3.08A7 7 0 012 9z"
            clipRule="evenodd"
          />
        </svg>
      </div>

      {filters.map((f) => {
        const active = activeFilters?.has(f.key);
        return (
          <button
            key={f.key}
            type="button"
            onClick={() => onToggleFilter?.(f.key)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition",
              active
                ? "border-brand-500 bg-brand-50 text-brand-700"
                : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50",
            )}
          >
            {f.label}
          </button>
        );
      })}

      {rightSlot && <div className="ml-auto flex items-center gap-2">{rightSlot}</div>}
    </div>
  );
}
