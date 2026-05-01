/** Odoo 19-style "Apps" launcher for KOB-ERP.
 *
 * - Light grey app background (matches Odoo's `o-bg-app`).
 * - Square white tiles with rounded corners + subtle border (no heavy shadows).
 * - Hover = purple border + slight lift, mirroring Odoo Apps card behaviour.
 * - Search + category chips up top.  Dark mode preserved.
 */

import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CATEGORIES, MODULES, type ModuleEntry } from "@/lib/modules";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark";

const THEME_STORAGE = "kob.home.theme";

function greetingKey(): string {
  const h = new Date().getHours();
  if (h < 12) return "home.greeting.morning";
  if (h < 17) return "home.greeting.afternoon";
  return "home.greeting.evening";
}

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [theme, setTheme] = useState<Theme>(
    (typeof localStorage !== "undefined" && (localStorage.getItem(THEME_STORAGE) as Theme)) || "light",
  );
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  useEffect(() => {
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(THEME_STORAGE, theme);
    }
    // Apply dark CSS-variable scope at document root so theme tokens flip too.
    if (typeof document !== "undefined") {
      document.documentElement.classList.toggle("kob-dark", theme === "dark");
    }
  }, [theme]);

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

  const dark = theme === "dark";
  const firstName = user?.full_name?.split(" ")[0] ?? "there";

  return (
    <div
      className={cn(
        // Break out of Layout's max-width so the launcher spans the viewport.
        "relative left-1/2 right-1/2 -mx-[50vw] -my-6 w-screen min-h-[calc(100vh-46px)] overflow-hidden px-4 py-8 transition-colors sm:px-8 lg:px-14",
        dark ? "bg-slate-950 text-slate-100" : "kob-apps-bg",
      )}
    >
      <div className="relative z-10 mx-auto w-full max-w-[1400px]">
        {/* Hero */}
        <header className="mb-7 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p
              className={cn(
                "text-[12px] font-medium uppercase tracking-[0.12em]",
                dark ? "text-slate-400" : "text-odoo-textMuted",
              )}
            >
              {t(greetingKey())}
              {user?.default_company ? ` · ${user.default_company.name}` : ""}
            </p>
            <h1 className="mt-1 text-[28px] font-semibold tracking-tight">
              {firstName}
            </h1>
            <p
              className={cn(
                "mt-1 max-w-md text-[13px]",
                dark ? "text-slate-400" : "text-odoo-textMuted",
              )}
            >
              {t("home.subtitle")}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <ThemeToggle theme={theme} onChange={setTheme} />
          </div>
        </header>

        {/* Search + filter chips */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-sm">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("home.searchApps")}
              className={cn(
                "w-full rounded border px-3 py-1.5 pl-9 text-[13px] transition",
                "focus:outline-none focus:ring-2",
                dark
                  ? "border-slate-700 bg-slate-900/80 text-slate-100 placeholder-slate-500 focus:border-brand-500 focus:ring-brand-500/40"
                  : "border-odoo-border bg-white text-odoo-text placeholder-odoo-textMuted focus:border-brand-500 focus:ring-brand-500/30",
              )}
            />
            <svg
              className={cn(
                "pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2",
                dark ? "text-slate-500" : "text-odoo-textMuted",
              )}
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
            <Chip
              dark={dark}
              active={activeCategory === null}
              onClick={() => setActiveCategory(null)}
            >
              {t("home.allApps")}
            </Chip>
            {CATEGORIES.map((c) => (
              <Chip
                key={c.id}
                dark={dark}
                active={activeCategory === c.id}
                onClick={() => setActiveCategory(c.id === activeCategory ? null : c.id)}
              >
                {t(c.labelKey)}
              </Chip>
            ))}
          </div>
        </div>

        {/* Empty state */}
        {filtered.length === 0 && (
          <div
            className={cn(
              "rounded border border-dashed px-6 py-16 text-center text-[13px]",
              dark
                ? "border-slate-700 text-slate-500"
                : "border-odoo-border text-odoo-textMuted",
            )}
          >
            {t("home.noResults")}
          </div>
        )}

        {/* Sections */}
        <div className="space-y-9">
          {CATEGORIES.map((cat) => {
            const items = grouped[cat.id] ?? [];
            if (items.length === 0) return null;
            return (
              <section key={cat.id}>
                <div className="mb-3 flex items-center gap-3">
                  <span
                    className={cn(
                      "text-[11px] font-semibold uppercase tracking-[0.18em]",
                      dark ? "text-slate-500" : "text-odoo-textMuted",
                    )}
                  >
                    {t(cat.labelKey)}
                  </span>
                  <span
                    className={cn(
                      "h-px flex-1",
                      dark ? "bg-slate-800" : "bg-odoo-border",
                    )}
                  />
                  <span
                    className={cn(
                      "text-[11px]",
                      dark ? "text-slate-500" : "text-odoo-textMuted",
                    )}
                  >
                    {items.length}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 xs:grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8">
                  {items.map((m, i) => (
                    <AppTile
                      key={m.key}
                      module={m}
                      dark={dark}
                      onClick={() => m.enabled && navigate(m.route)}
                      delayMs={i * 25}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>

        <div
          className={cn(
            "mt-10 text-center text-[11px]",
            dark ? "text-slate-600" : "text-odoo-textMuted",
          )}
        >
          KOB-ERP · {new Date().toLocaleDateString(i18n.language)}
        </div>
      </div>
    </div>
  );
}

interface ChipProps {
  active: boolean;
  dark: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function Chip({ active, dark, onClick, children }: ChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition",
        active
          ? dark
            ? "border-brand-500 bg-brand-500/20 text-brand-200"
            : "border-brand-500 bg-brand-50 text-brand-700"
          : dark
          ? "border-slate-700 bg-slate-900/80 text-slate-400 hover:bg-slate-800"
          : "border-odoo-border bg-white text-odoo-textMuted hover:bg-odoo-mutedBg",
      )}
    >
      {children}
    </button>
  );
}

interface AppTileProps {
  module: ModuleEntry;
  dark: boolean;
  onClick: () => void;
  delayMs: number;
}

function AppTile({ module, dark, onClick, delayMs }: AppTileProps) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!module.enabled}
      style={{ animationDelay: `${delayMs}ms` }}
      className={cn(
        "group relative flex animate-float-in flex-col items-center justify-end overflow-hidden p-3 text-left transition",
        "h-32 sm:h-36",
        module.enabled ? "cursor-pointer" : "cursor-not-allowed opacity-60",
        dark
          ? "rounded-xl bg-slate-900/60 ring-1 ring-slate-800 hover:bg-slate-900 hover:ring-slate-700"
          : "kob-app-tile",
      )}
    >
      <div
        className={cn(
          "absolute left-1/2 top-3 grid h-12 w-12 -translate-x-1/2 place-items-center rounded-xl bg-gradient-to-br shadow-sm transition group-hover:scale-105",
          module.gradient,
        )}
      >
        <span className="text-[18px] font-bold text-white">{module.iconLabel}</span>
      </div>

      <div
        className={cn(
          "mt-auto w-full text-center",
          dark ? "text-slate-100" : "text-odoo-text",
        )}
      >
        <div className="truncate text-[13px] font-semibold">{module.name}</div>
        <div
          className={cn(
            "mt-0.5 truncate text-[10px]",
            dark ? "text-slate-500" : "text-odoo-textMuted",
          )}
        >
          {module.enabled ? `Phase ${module.phase}` : t("home.comingSoon")}
        </div>
      </div>
    </button>
  );
}

interface ThemeToggleProps {
  theme: Theme;
  onChange: (next: Theme) => void;
}

function ThemeToggle({ theme, onChange }: ThemeToggleProps) {
  const { t } = useTranslation();
  return (
    <div
      className={cn(
        "inline-flex rounded-full border p-0.5 text-[11px] font-medium",
        theme === "dark"
          ? "border-slate-700 bg-slate-900/80 text-slate-300"
          : "border-odoo-border bg-white text-odoo-textMuted",
      )}
    >
      {(["light", "dark"] as Theme[]).map((mode) => (
        <button
          key={mode}
          type="button"
          onClick={() => onChange(mode)}
          className={cn(
            "rounded-full px-2.5 py-0.5 transition",
            theme === mode
              ? mode === "dark"
                ? "bg-slate-700 text-white"
                : "bg-brand-500 text-white"
              : "hover:bg-odoo-mutedBg",
          )}
        >
          {mode === "dark" ? "🌙" : "☀️"} {t(`home.theme.${mode}`)}
        </button>
      ))}
    </div>
  );
}
