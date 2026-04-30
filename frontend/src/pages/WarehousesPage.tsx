import { useQuery } from "@tanstack/react-query";
import { wmsApi } from "@/lib/wms";

export default function WarehousesPage() {
  const warehouses = useQuery({ queryKey: ["warehouses"], queryFn: wmsApi.warehouses });

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Warehouses</h1>
      <p className="mt-1 text-sm text-slate-500">Physical sites and their zones.</p>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {warehouses.isLoading && (
          <div className="col-span-full rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-400">
            Loading…
          </div>
        )}
        {warehouses.data?.length === 0 && (
          <div className="col-span-full rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-400">
            No warehouses yet — create one via <code>POST /api/v1/wms/warehouses</code>
          </div>
        )}
        {warehouses.data?.map((wh) => (
          <div
            key={wh.id}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="text-xs font-mono uppercase tracking-wider text-brand-600">
              {wh.code}
            </div>
            <div className="mt-1 text-lg font-semibold text-slate-900">{wh.name}</div>
            {wh.address && (
              <p className="mt-2 text-sm text-slate-600 whitespace-pre-line">{wh.address}</p>
            )}
            {!wh.active && (
              <p className="mt-2 text-xs font-medium text-rose-600">INACTIVE</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
