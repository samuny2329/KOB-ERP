/** Public preview of the home launcher — no auth, no backend.
 *
 * Mounts HomePage's UI shell with synthetic delays so the per-module
 * skeletons render long enough to evaluate.  Remove or gate behind a dev
 * flag once the real backend is provisioned.
 */

import { useEffect, useState } from "react";
import { MODULES } from "@/lib/modules";
import { ModuleCard } from "@/components/ModuleCard";

const MOCK_METRICS: Record<string, { primary: string | number; secondary: string }> = {
  products: { primary: 1284, secondary: "active SKUs" },
  warehouses: { primary: 3, secondary: "sites" },
  transfers: { primary: 47, secondary: "this week" },
  stock: { primary: "12.4k", secondary: "quant rows" },
  lots: { primary: 218, secondary: "lots tracked" },
  outbound: { primary: 91, secondary: "in pick / pack" },
  couriers: { primary: 6, secondary: "active carriers" },
};

export default function PreviewHomePage() {
  // Fake the loading window to showcase the skeletons.
  const [loaded, setLoaded] = useState<Set<string>>(new Set());

  useEffect(() => {
    const timers = MODULES.map((m, i) =>
      setTimeout(() => {
        setLoaded((s) => new Set([...s, m.key]));
      }, 600 + i * 180),
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-10">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <h1 className="text-3xl font-semibold text-slate-900">Hi, Sivaporn</h1>
            <p className="mt-1 text-sm text-slate-500">
              Pick a module to jump in.  Tiles show live counts; click to open.
            </p>
            <span className="mt-2 inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              Preview mode — no auth, mock data
            </span>
          </div>
          <div className="hidden text-right text-xs text-slate-400 sm:block">
            {new Date().toLocaleDateString(undefined, {
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </div>
        </div>

        <div className="grid auto-rows-[140px] grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {MODULES.map((m, i) => {
            const loading = !loaded.has(m.key);
            const metric = !loading ? MOCK_METRICS[m.key] : undefined;
            return (
              <ModuleCard
                key={m.key}
                module={m}
                index={i}
                loading={loading}
                metric={metric}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
