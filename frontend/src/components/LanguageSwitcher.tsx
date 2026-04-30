/** Toggle between Thai and English (persists to localStorage via i18next). */

import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

const LOCALES = [
  { code: "th", label: "ไทย" },
  { code: "en", label: "EN" },
];

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  return (
    <div className="inline-flex rounded-md border border-slate-300 bg-white p-0.5 text-[11px] font-medium">
      {LOCALES.map((l) => (
        <button
          key={l.code}
          type="button"
          onClick={() => void i18n.changeLanguage(l.code)}
          className={cn(
            "rounded px-2 py-0.5 transition",
            i18n.language?.startsWith(l.code)
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-100",
          )}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
