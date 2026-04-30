/** Bento-style app launcher — replaces the classic "icons in a grid". */

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { MODULES } from "@/lib/modules";
import { wmsApi, inventoryApi } from "@/lib/wms";
import { ModuleCard } from "@/components/ModuleCard";

function useArtificialMinDuration(query: { isLoading: boolean }, ms = 600): boolean {
  const [holding, setHolding] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setHolding(false), ms);
    return () => clearTimeout(t);
  }, [ms]);
  return query.isLoading || holding;
}

export default function HomePage() {
  const { user } = useAuth();

  // Live metrics — each module computes its own count.
  const products = useQuery({
    queryKey: ["metric", "products"],
    queryFn: () => wmsApi.products({ limit: 1 }).then((r) => r.length),
  });
  const warehouses = useQuery({
    queryKey: ["metric", "warehouses"],
    queryFn: () => wmsApi.warehouses().then((r) => r.length),
  });
  const transfers = useQuery({
    queryKey: ["metric", "transfers"],
    queryFn: () => inventoryApi.transfers({ limit: 50 }).then((r) => r.length),
  });
  const stock = useQuery({
    queryKey: ["metric", "quants"],
    queryFn: () => inventoryApi.quants().then((r) => r.length),
  });
  const lots = useQuery({
    queryKey: ["metric", "lots"],
    queryFn: () => wmsApi.lots().then((r) => r.length),
  });

  // Hold every card in the skeleton state for at least 600ms so the load
  // animation reads as intentional, not as a flicker.
  const productsLoading = useArtificialMinDuration(products);
  const warehousesLoading = useArtificialMinDuration(warehouses);
  const transfersLoading = useArtificialMinDuration(transfers);
  const stockLoading = useArtificialMinDuration(stock);
  const lotsLoading = useArtificialMinDuration(lots);

  const metricByKey: Record<
    string,
    { loading: boolean; metric?: { primary: string | number; secondary?: string } }
  > = {
    products: {
      loading: productsLoading,
      metric: products.data !== undefined ? { primary: products.data, secondary: "active SKUs" } : undefined,
    },
    warehouses: {
      loading: warehousesLoading,
      metric:
        warehouses.data !== undefined
          ? { primary: warehouses.data, secondary: warehouses.data === 1 ? "site" : "sites" }
          : undefined,
    },
    transfers: {
      loading: transfersLoading,
      metric:
        transfers.data !== undefined
          ? { primary: transfers.data, secondary: "recent transfers" }
          : undefined,
    },
    stock: {
      loading: stockLoading,
      metric: stock.data !== undefined ? { primary: stock.data, secondary: "quant rows" } : undefined,
    },
    lots: {
      loading: lotsLoading,
      metric: lots.data !== undefined ? { primary: lots.data, secondary: "lots" } : undefined,
    },
  };

  return (
    <div>
      <div className="mb-8 flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-slate-900">
            Hi, {user?.full_name?.split(" ")[0] ?? "there"}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Pick a module to jump in.  Tiles show live counts; click to open.
          </p>
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
          const entry = metricByKey[m.key];
          return (
            <ModuleCard
              key={m.key}
              module={m}
              index={i}
              loading={entry?.loading ?? false}
              metric={entry?.metric}
            />
          );
        })}
      </div>
    </div>
  );
}
