/** Bento-style live tile that links to a module.
 *
 * While data is loading the card shows a skeleton sized & shaped like the
 * module's eventual content (driven by `module.skeleton`).  When data is
 * ready the skeleton fades out and a metric chunk fades in.
 */

import { useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { type ModuleEntry, SIZE_CLASSES } from "@/lib/modules";
import { Skeleton } from "@/components/Skeletons";

interface ModuleCardProps {
  module: ModuleEntry;
  loading: boolean;
  metric?: { primary: string | number; secondary?: string };
  index?: number;
}

export function ModuleCard({ module, loading, metric, index = 0 }: ModuleCardProps) {
  const navigate = useNavigate();
  const interactive = module.enabled;

  return (
    <button
      type="button"
      disabled={!interactive}
      onClick={() => interactive && navigate(module.route)}
      style={{ animationDelay: `${index * 50}ms` }}
      className={cn(
        "group relative flex flex-col justify-between overflow-hidden rounded-2xl p-5 text-left text-white shadow-lg shadow-black/5 ring-1 ring-white/10",
        "bg-gradient-to-br",
        module.gradient,
        SIZE_CLASSES[module.size],
        "min-h-32 sm:min-h-36 transition-all duration-300",
        "animate-float-in",
        interactive
          ? "hover:scale-[1.02] hover:shadow-2xl hover:ring-white/30 active:scale-[0.99]"
          : "cursor-not-allowed opacity-60 grayscale-[40%]",
      )}
    >
      {/* Decorative blurred orb that drifts on hover */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-10 -right-8 h-32 w-32 rounded-full bg-white/20 blur-2xl transition-transform duration-500 group-hover:translate-x-2 group-hover:-translate-y-1"
      />

      <header className="relative flex items-start justify-between">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/15 text-lg font-bold backdrop-blur-sm ring-1 ring-white/20">
          {module.iconLabel}
        </div>
        <span className="rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider backdrop-blur-sm">
          Phase {module.phase}
        </span>
      </header>

      <div className="relative mt-4 flex-1">
        {loading ? (
          <Skeleton kind={module.skeleton} />
        ) : metric ? (
          <div className="flex h-full flex-col justify-end animate-float-in">
            <div className="text-3xl font-semibold leading-none tabular-nums sm:text-4xl">
              {metric.primary}
            </div>
            {metric.secondary && (
              <div className="mt-1 text-xs opacity-80">{metric.secondary}</div>
            )}
          </div>
        ) : (
          <Skeleton kind={module.skeleton} />
        )}
      </div>

      <footer className="relative mt-4 space-y-0.5">
        <div className="text-base font-semibold">{module.name}</div>
        <div className={cn("text-xs opacity-90", module.accent)}>
          {interactive ? module.description : "Coming soon"}
        </div>
      </footer>
    </button>
  );
}
