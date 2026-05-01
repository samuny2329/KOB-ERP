/** Cross-company Vendor 360 — group profiles + spend + score + rebates. */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ListView, SearchBar, Sheet, type Column } from "@/components/views";
import { groupApi, type CrossCompanyVendor } from "@/lib/group";
import { cn } from "@/lib/utils";

function ScoreBar({ value, color = "emerald" }: { value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn("h-full", `bg-${color}-500`)}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-slate-600">{value.toFixed(0)}%</span>
    </div>
  );
}

export default function CrossCompanyVendorsPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const vendors = useQuery({ queryKey: ["xc-vendors"], queryFn: groupApi.vendors });
  const accruals = useQuery({
    queryKey: ["rebate-accruals"],
    queryFn: () => groupApi.rebateAccruals(),
  });

  const accrualByVendor = new Map<number, number>();
  for (const a of accruals.data ?? []) {
    accrualByVendor.set(
      a.vendor_profile_id,
      (accrualByVendor.get(a.vendor_profile_id) ?? 0) + a.accrued_rebate,
    );
  }

  const filtered = (vendors.data ?? []).filter(
    (v) =>
      !search ||
      `${v.group_code} ${v.name} ${v.tax_id ?? ""}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );

  const columns: Column<CrossCompanyVendor>[] = [
    {
      key: "group_code",
      header: t("xc.code", "Group code"),
      render: (v) => <div className="font-mono text-xs">{v.group_code}</div>,
    },
    {
      key: "name",
      header: t("xc.name", "Name"),
      render: (v) => (
        <div>
          <div className="font-medium text-slate-900">{v.name}</div>
          {v.legal_name && (
            <div className="text-xs text-slate-500">{v.legal_name}</div>
          )}
        </div>
      ),
    },
    {
      key: "ytd",
      header: t("xc.ytdSpend", "YTD spend"),
      className: "text-right tabular-nums",
      render: (v) => (
        <div className="text-right">
          <div className="text-sm font-semibold">
            ฿{v.ytd_spend.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="text-xs text-slate-500">
            ฿{v.lifetime_spend.toLocaleString(undefined, { maximumFractionDigits: 0 })} lifetime
          </div>
        </div>
      ),
    },
    {
      key: "otd",
      header: t("xc.otd", "OTD"),
      render: (v) => <ScoreBar value={v.group_otd_pct} color="emerald" />,
    },
    {
      key: "quality",
      header: t("xc.quality", "Quality"),
      render: (v) => <ScoreBar value={v.group_quality_pct} color="sky" />,
    },
    {
      key: "score",
      header: t("xc.score", "Score"),
      className: "text-right",
      render: (v) => (
        <div className="text-right text-sm font-semibold tabular-nums">
          {v.group_score.toFixed(0)}
        </div>
      ),
    },
    {
      key: "rebate",
      header: t("xc.rebate", "Rebate accrued"),
      className: "text-right",
      render: (v) => {
        const r = accrualByVendor.get(v.id) ?? 0;
        return (
          <div className="text-right">
            <div className="text-sm font-semibold tabular-nums">
              {r > 0 ? `฿${r.toLocaleString()}` : "—"}
            </div>
          </div>
        );
      },
    },
    {
      key: "links",
      header: t("xc.companies", "Companies"),
      render: (v) => (
        <div className="flex flex-wrap gap-1">
          {v.links.map((l) => (
            <span
              key={l.id}
              className={cn(
                "rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700",
                l.is_primary && "ring-1 ring-emerald-400",
              )}
            >
              #{l.company_id}
            </span>
          ))}
          {v.links.length === 0 && <span className="text-xs text-slate-400">—</span>}
        </div>
      ),
    },
  ];

  return (
    <Sheet
      title={t("xc.vendors.title", "Cross-company vendors")}
      subtitle={t(
        "xc.vendors.subtitle",
        "One profile per supplier — group spend drives volume rebates and supplier scoring",
      )}
    >
      <SearchBar value={search} onChange={setSearch} />

      <ListView
        rows={filtered}
        columns={columns}
        loading={vendors.isLoading}
        rowKey={(v) => v.id}
      />
    </Sheet>
  );
}
