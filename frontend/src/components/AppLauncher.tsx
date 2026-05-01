/** Enterprise launchpad overlay (SAP Fiori-style).
 *
 * Click the ⊞ button in the navbar → fullscreen overlay opens with the
 * complete tile grid (grouped by category, with search).  Esc / click
 * backdrop / pick an app → close.  Same UX pattern that SAP Launchpad,
 * Salesforce App Launcher and Odoo Apps all share — re-skinned for KOB-ERP.
 */

import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CATEGORIES, MODULES, type ModuleEntry } from "@/lib/modules";
import { cn } from "@/lib/utils";

interface AppLauncherProps {
  open: boolean;
  onClose: () => void;
}

export function AppLauncher({ open, onClose }: AppLauncherProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  // Close on Esc + lock body scroll while open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return MODULES.filter((m) => {
      if (activeCategory && m.category !== activeCategory) return false;
      if (q && !`${m.name} ${m.description} ${m.iconLabel}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [search, activeCategory]);

  const grouped = useMemo(() => {
    const buckets: Record<string, ModuleEntry[]> = {};
    for (const m of filtered) {
      const key = m.category ?? "core";
      (buckets[key] ??= []).push(m);
    }
    return buckets;
  }, [filtered]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Application launcher"
      className="fixed inset-0 z-50 animate-float-in bg-white/95 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Top strip: brand + close */}
      <div
        className="kob-navbar"
        style={{ backgroundColor: "var(--o-brand-primary)" }}
      >
        <div className="mx-auto flex h-full w-full max-w-[1600px] items-stretch px-3">
          <div className="kob-brand">
            <span className="kob-brand-mark">K</span>
            <span className="whitespace-nowrap text-[15px]">KOB-ERP · Apps</span>
          </div>
          <div className="flex-1" />
          <button
            type="button"
            onClick={onClose}
            className="self-center rounded border border-white/30 px-3 py-1 text-[12px] text-white/95 hover:bg-black/20"
          >
            ✕  Close
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-[1400px] px-6 py-8">
        {/* Search + chips */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-md">
            <input
              autoFocus
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e: KeyboardEvent<HTMLInputElement>) => {
                if (e.key === "Enter" && filtered.length > 0 && filtered[0].enabled) {
                  navigate(filtered[0].route);
                  onClose();
                }
              }}
              placeholder={t("home.searchApps")}
              className="w-full rounded border border-odoo-border bg-white px-3 py-2 pl-9 text-[14px] text-odoo-text placeholder-odoo-textMuted focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            />
            <svg
              className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-odoo-textMuted"
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

          <div className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              onClick={() => setActiveCategory(null)}
              className={cn(
                "rounded-full border px-3 py-1 text-[12px] font-medium transition",
                activeCategory === null
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-odoo-border bg-white text-odoo-textMuted hover:bg-odoo-mutedBg",
              )}
            >
              {t("home.allApps")}
            </button>
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setActiveCategory(c.id === activeCategory ? null : c.id)}
                className={cn(
                  "rounded-full border px-3 py-1 text-[12px] font-medium transition",
                  activeCategory === c.id
                    ? "border-brand-500 bg-brand-50 text-brand-700"
                    : "border-odoo-border bg-white text-odoo-textMuted hover:bg-odoo-mutedBg",
                )}
              >
                {t(c.labelKey)}
              </button>
            ))}
          </div>
        </div>

        {/* Sections */}
        {filtered.length === 0 && (
          <div className="rounded border border-dashed border-odoo-border px-6 py-16 text-center text-[13px] text-odoo-textMuted">
            {t("home.noResults")}
          </div>
        )}

        <div className="space-y-8">
          {CATEGORIES.map((cat) => {
            const items = grouped[cat.id] ?? [];
            if (items.length === 0) return null;
            return (
              <section key={cat.id}>
                <div className="mb-3 flex items-center gap-3">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-odoo-textMuted">
                    {t(cat.labelKey)}
                  </span>
                  <span className="h-px flex-1 bg-odoo-border" />
                  <span className="text-[11px] text-odoo-textMuted">{items.length}</span>
                </div>

                <div className="grid grid-cols-2 gap-3 xs:grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8">
                  {items.map((m, i) => (
                    <button
                      key={m.key}
                      type="button"
                      disabled={!m.enabled}
                      onClick={() => {
                        if (m.enabled) {
                          navigate(m.route);
                          onClose();
                        }
                      }}
                      style={{ animationDelay: `${i * 18}ms` }}
                      className={cn(
                        "group relative flex h-32 animate-float-in flex-col items-center justify-end overflow-hidden p-3 text-left transition sm:h-36",
                        m.enabled ? "kob-app-tile cursor-pointer" : "kob-app-tile cursor-not-allowed opacity-60",
                      )}
                    >
                      <div
                        className={cn(
                          "absolute left-1/2 top-3 grid h-12 w-12 -translate-x-1/2 place-items-center rounded-xl bg-gradient-to-br shadow-sm transition group-hover:scale-105",
                          m.gradient,
                        )}
                      >
                        <span className="text-[18px] font-bold text-white">{m.iconLabel}</span>
                      </div>
                      <div className="mt-auto w-full text-center text-odoo-text">
                        <div className="truncate text-[13px] font-semibold">{m.name}</div>
                        <div className="mt-0.5 truncate text-[10px] text-odoo-textMuted">
                          {m.enabled ? `Phase ${m.phase}` : t("home.comingSoon")}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
