import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { wmsApi } from "@/lib/wms";

export default function ProductsPage() {
  const [q, setQ] = useState("");
  const products = useQuery({
    queryKey: ["products", q],
    queryFn: () => wmsApi.products({ q: q || undefined, limit: 100 }),
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Products</h1>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search SKU or name…"
          className="w-72 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <table className="min-w-full divide-y divide-slate-200">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-2.5">SKU</th>
              <th className="px-4 py-2.5">Name</th>
              <th className="px-4 py-2.5">Type</th>
              <th className="px-4 py-2.5 text-right">List price</th>
              <th className="px-4 py-2.5 text-right">Cost</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {products.isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            )}
            {products.isError && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-rose-600">
                  Failed to load products
                </td>
              </tr>
            )}
            {products.data?.length === 0 && !products.isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  No products yet
                </td>
              </tr>
            )}
            {products.data?.map((p) => (
              <tr key={p.id} className="hover:bg-slate-50">
                <td className="px-4 py-2.5 font-mono text-xs">{p.default_code}</td>
                <td className="px-4 py-2.5">{p.name}</td>
                <td className="px-4 py-2.5 text-slate-600">{p.type}</td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  {p.list_price.toFixed(2)}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums text-slate-600">
                  {p.standard_price.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
