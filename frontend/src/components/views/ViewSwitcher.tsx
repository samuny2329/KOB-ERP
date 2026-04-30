/** Pill toggle between list / kanban (and any future view types). */

import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

export type ViewMode = "list" | "kanban";

interface ViewSwitcherProps {
  value: ViewMode;
  onChange: (next: ViewMode) => void;
  available?: ViewMode[];
}

export function ViewSwitcher({
  value,
  onChange,
  available = ["list", "kanban"],
}: ViewSwitcherProps) {
  const { t } = useTranslation();
  return (
    <div className="inline-flex rounded-md border border-slate-300 bg-white p-0.5 text-xs">
      {available.map((mode) => (
        <button
          key={mode}
          type="button"
          onClick={() => onChange(mode)}
          className={cn(
            "rounded px-2.5 py-1 transition",
            value === mode
              ? "bg-slate-900 text-white shadow-sm"
              : "text-slate-600 hover:bg-slate-100",
          )}
        >
          {t(`view.${mode}`)}
        </button>
      ))}
    </div>
  );
}
