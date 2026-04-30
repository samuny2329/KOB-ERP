/** Central registry of every KOB-ERP module shown on the home launcher.
 *
 * Each entry drives:
 *   - the bento card on /home (color, gradient, icon, size)
 *   - the skeleton variant rendered while data loads
 *   - the route the card links to
 *
 * Add a new entry whenever a phase ships another module (Phase 2b/2c/etc).
 */

export type SkeletonKind =
  | "barcode" // products
  | "boxes" // warehouses
  | "rows" // transfers / orders
  | "shelf" // inventory / quants
  | "tags" // categories / generic master data
  | "package" // outbound / dispatch
  | "users"; // hr / accounts

export type CardSize = "sm" | "md" | "lg" | "wide" | "tall";

export interface ModuleEntry {
  key: string;
  name: string;
  description: string;
  route: string;
  size: CardSize;
  /** Tailwind gradient classes — applied as the card background. */
  gradient: string;
  /** Tailwind text colour for the icon glyph + headings. */
  accent: string;
  iconLabel: string; // single-letter glyph; replace with SVG icons later
  skeleton: SkeletonKind;
  phase: string;
  enabled: boolean;
}

export const MODULES: ModuleEntry[] = [
  {
    key: "products",
    name: "Products",
    description: "SKU master, categories, lots",
    route: "/products",
    size: "lg",
    gradient: "from-sky-500/90 via-sky-600 to-sky-700",
    accent: "text-sky-50",
    iconLabel: "P",
    skeleton: "barcode",
    phase: "2a",
    enabled: true,
  },
  {
    key: "warehouses",
    name: "Warehouses",
    description: "Sites, zones, locations",
    route: "/warehouses",
    size: "md",
    gradient: "from-emerald-500/90 via-emerald-600 to-emerald-700",
    accent: "text-emerald-50",
    iconLabel: "W",
    skeleton: "boxes",
    phase: "2a",
    enabled: true,
  },
  {
    key: "transfers",
    name: "Transfers",
    description: "Inbound, outbound, internal moves",
    route: "/transfers",
    size: "wide",
    gradient: "from-violet-500/90 via-violet-600 to-violet-700",
    accent: "text-violet-50",
    iconLabel: "T",
    skeleton: "rows",
    phase: "2a",
    enabled: true,
  },
  {
    key: "stock",
    name: "On-hand stock",
    description: "Quants by location & lot",
    route: "/stock",
    size: "md",
    gradient: "from-amber-500/90 via-amber-600 to-amber-700",
    accent: "text-amber-50",
    iconLabel: "S",
    skeleton: "shelf",
    phase: "2a",
    enabled: true,
  },
  {
    key: "lots",
    name: "Lots & Serials",
    description: "Traceability, expiry alerts",
    route: "/lots",
    size: "sm",
    gradient: "from-rose-500/90 via-rose-600 to-rose-700",
    accent: "text-rose-50",
    iconLabel: "L",
    skeleton: "tags",
    phase: "2a",
    enabled: true,
  },
  {
    key: "outbound",
    name: "Outbound",
    description: "Pick / Pack / Ship orders",
    route: "/outbound",
    size: "tall",
    gradient: "from-fuchsia-500/90 via-fuchsia-600 to-fuchsia-700",
    accent: "text-fuchsia-50",
    iconLabel: "O",
    skeleton: "package",
    phase: "2b",
    enabled: true,
  },
  {
    key: "couriers",
    name: "Couriers & Dispatch",
    description: "Carriers, batches, AWBs",
    route: "/couriers",
    size: "md",
    gradient: "from-cyan-500/90 via-cyan-600 to-cyan-700",
    accent: "text-cyan-50",
    iconLabel: "C",
    skeleton: "package",
    phase: "2b",
    enabled: true,
  },
  {
    key: "counts",
    name: "Cycle Counts",
    description: "Sessions, tasks, variance",
    route: "/counts",
    size: "sm",
    gradient: "from-indigo-500/90 via-indigo-600 to-indigo-700",
    accent: "text-indigo-50",
    iconLabel: "#",
    skeleton: "shelf",
    phase: "2c",
    enabled: false,
  },
  {
    key: "purchase",
    name: "Purchase",
    description: "Vendors, POs, receipts",
    route: "/purchase",
    size: "sm",
    gradient: "from-teal-500/90 via-teal-600 to-teal-700",
    accent: "text-teal-50",
    iconLabel: "$",
    skeleton: "rows",
    phase: "3",
    enabled: false,
  },
  {
    key: "manufacturing",
    name: "Manufacturing",
    description: "BoM, MO, subcon",
    route: "/manufacturing",
    size: "sm",
    gradient: "from-orange-500/90 via-orange-600 to-orange-700",
    accent: "text-orange-50",
    iconLabel: "M",
    skeleton: "rows",
    phase: "3",
    enabled: false,
  },
  {
    key: "accounting",
    name: "Accounting",
    description: "GL, journals, AP/AR",
    route: "/accounting",
    size: "sm",
    gradient: "from-slate-700 via-slate-800 to-slate-900",
    accent: "text-slate-100",
    iconLabel: "₿",
    skeleton: "rows",
    phase: "5",
    enabled: false,
  },
  {
    key: "hr",
    name: "HR",
    description: "Employees, payroll",
    route: "/hr",
    size: "sm",
    gradient: "from-pink-500/90 via-pink-600 to-pink-700",
    accent: "text-pink-50",
    iconLabel: "H",
    skeleton: "users",
    phase: "6",
    enabled: false,
  },
];

export function findModule(key: string): ModuleEntry | undefined {
  return MODULES.find((m) => m.key === key);
}

export const SIZE_CLASSES: Record<CardSize, string> = {
  sm: "col-span-1 row-span-1",
  md: "col-span-1 row-span-1 sm:col-span-2",
  lg: "col-span-1 row-span-2 sm:col-span-2",
  wide: "col-span-1 row-span-1 sm:col-span-3",
  tall: "col-span-1 row-span-2",
};
