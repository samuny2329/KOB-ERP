/** Per-module skeleton variants used inside ModuleCard while data loads.
 *
 * Each variant matches the *shape* of what's about to render, so the
 * transition from skeleton → real data is visually stable.  Animations
 * are pure Tailwind (animate-pulse) — no extra deps.
 */

import { cn } from "@/lib/utils";
import type { SkeletonKind } from "@/lib/modules";

const baseShimmer =
  "relative overflow-hidden before:absolute before:inset-0 before:-translate-x-full before:animate-[shimmer_1.6s_infinite] before:bg-gradient-to-r before:from-transparent before:via-white/30 before:to-transparent";

function Bar({ className }: { className?: string }) {
  return <div className={cn("rounded bg-white/25", baseShimmer, className)} />;
}

export function BarcodeSkeleton() {
  // Stripes that look like a barcode + a price tag underneath.
  return (
    <div className="flex h-full flex-col justify-end gap-2">
      <div className="flex items-end gap-1">
        {[3, 2, 4, 1, 3, 5, 2, 3, 1, 4, 2, 3, 5, 2].map((w, i) => (
          <div
            key={i}
            className={cn(
              "rounded-sm bg-white/35 animate-pulse",
              `h-${4 + (i % 3) * 2}`,
            )}
            style={{ width: `${w * 2}px`, height: `${20 + (i % 4) * 6}px` }}
          />
        ))}
      </div>
      <Bar className="h-3 w-1/2" />
      <Bar className="h-2 w-1/3" />
    </div>
  );
}

export function BoxesSkeleton() {
  return (
    <div className="grid h-full grid-cols-3 gap-2">
      {Array.from({ length: 6 }, (_, i) => (
        <div
          key={i}
          className={cn(
            "aspect-square rounded-md bg-white/25 animate-pulse",
            i % 2 === 0 ? "delay-75" : "delay-150",
          )}
        />
      ))}
    </div>
  );
}

export function RowsSkeleton() {
  return (
    <div className="flex h-full flex-col justify-center gap-2">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="flex items-center gap-2">
          <div className="h-2.5 flex-1 rounded bg-white/25 animate-pulse" />
          <div
            className={cn(
              "h-2.5 rounded-full bg-white/35 animate-pulse",
              i % 2 === 0 ? "w-12" : "w-8",
            )}
          />
        </div>
      ))}
    </div>
  );
}

export function ShelfSkeleton() {
  return (
    <div className="flex h-full flex-col justify-end gap-1.5">
      {Array.from({ length: 3 }, (_, row) => (
        <div key={row} className="flex gap-1.5">
          {Array.from({ length: 5 }, (_, col) => (
            <div
              key={col}
              className="h-5 flex-1 rounded-sm bg-white/25 animate-pulse"
              style={{ animationDelay: `${(row * 5 + col) * 80}ms` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

export function TagsSkeleton() {
  return (
    <div className="flex h-full flex-wrap content-end gap-1.5">
      {[20, 14, 18, 12, 22, 10, 16].map((w, i) => (
        <div
          key={i}
          className="h-5 rounded-full bg-white/30 animate-pulse"
          style={{ width: `${w * 4}px`, animationDelay: `${i * 100}ms` }}
        />
      ))}
    </div>
  );
}

export function PackageSkeleton() {
  // Conveyor belt — boxes sliding right with staggered pulse.
  return (
    <div className="relative h-full">
      <div className="absolute inset-x-0 top-1/2 h-px bg-white/20" />
      <div className="flex h-full items-center gap-3">
        {Array.from({ length: 4 }, (_, i) => (
          <div
            key={i}
            className="relative h-10 w-10 rounded-md bg-white/30 animate-pulse"
            style={{ animationDelay: `${i * 200}ms` }}
          >
            <div className="absolute inset-x-2 top-1.5 h-1 rounded bg-white/40" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function UsersSkeleton() {
  return (
    <div className="flex h-full flex-col justify-center gap-2">
      {Array.from({ length: 3 }, (_, i) => (
        <div key={i} className="flex items-center gap-2">
          <div
            className="h-8 w-8 rounded-full bg-white/30 animate-pulse"
            style={{ animationDelay: `${i * 120}ms` }}
          />
          <div className="flex-1 space-y-1">
            <div className="h-2.5 w-2/3 rounded bg-white/25 animate-pulse" />
            <div className="h-2 w-1/3 rounded bg-white/20 animate-pulse" />
          </div>
        </div>
      ))}
    </div>
  );
}

const VARIANTS: Record<SkeletonKind, () => JSX.Element> = {
  barcode: BarcodeSkeleton,
  boxes: BoxesSkeleton,
  rows: RowsSkeleton,
  shelf: ShelfSkeleton,
  tags: TagsSkeleton,
  package: PackageSkeleton,
  users: UsersSkeleton,
};

export function Skeleton({ kind }: { kind: SkeletonKind }) {
  const Variant = VARIANTS[kind];
  return <Variant />;
}
