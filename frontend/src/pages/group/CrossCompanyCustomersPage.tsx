/** Cross-company Customer 360 — group profiles + per-company links + LTV. */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { ListView, SearchBar, Sheet, type Column } from "@/components/views";
import { groupApi, type CrossCompanyCustomer } from "@/lib/group";
import { cn } from "@/lib/utils";
import { useState } from "react";

const GROUP_BADGE: Record<string, string> = {
  vip: "bg-amber-100 text-amber-800",
  regular: "bg-slate-100 text-slate-700",
  wholesale: "bg-violet-100 text-violet-800",
  retail: "bg-sky-100 text-sky-800",
};

export default function CrossCompanyCustomersPage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const customers = useQuery({ queryKey: ["xc-customers"], queryFn: groupApi.customers });

  const filtered = (customers.data ?? []).filter(
    (c) =>
      !search ||
      `${c.group_code} ${c.name} ${c.tax_id ?? ""} ${c.primary_email ?? ""}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );

  const columns: Column<CrossCompanyCustomer>[] = [
    {
      key: "group_code",
      header: t("xc.code", "Group code"),
      render: (c) => (
        <div className="font-mono text-xs">{c.group_code}</div>
      ),
    },
    {
      key: "name",
      header: t("xc.name", "Name"),
      render: (c) => (
        <div>
          <div className="font-medium text-slate-900">{c.name}</div>
          {c.legal_name && (
            <div className="text-xs text-slate-500">{c.legal_name}</div>
          )}
        </div>
      ),
    },
    {
      key: "group",
      header: t("xc.tier", "Tier"),
      render: (c) => (
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-medium",
            GROUP_BADGE[c.customer_group] ?? "bg-slate-100 text-slate-700",
          )}
        >
          {c.customer_group}
        </span>
      ),
    },
    {
      key: "credit",
      header: t("xc.credit", "Credit (group-wide)"),
      className: "text-right",
      render: (c) => {
        const remaining = c.group_credit_limit - c.group_credit_consumed;
        const usedPct =
          c.group_credit_limit > 0
            ? (c.group_credit_consumed / c.group_credit_limit) * 100
            : 0;
        return (
          <div className="text-right">
            <div className="text-sm font-semibold tabular-nums">
              ฿{remaining.toLocaleString()}
            </div>
            <div className="text-xs text-slate-500 tabular-nums">
              {c.group_credit_limit > 0
                ? `${usedPct.toFixed(0)}% of ฿${c.group_credit_limit.toLocaleString()}`
                : t("xc.unlimited", "unlimited")}
            </div>
          </div>
        );
      },
    },
    {
      key: "ltv",
      header: t("xc.ltv", "LTV score"),
      className: "text-right tabular-nums",
      render: (c) => (
        <div className="text-right">
          <div className="text-sm font-semibold">
            ฿{c.group_ltv_score.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
      ),
    },
    {
      key: "links",
      header: t("xc.companies", "Companies"),
      render: (c) => (
        <div className="flex flex-wrap gap-1">
          {c.links.length === 0 ? (
            <span className="text-xs text-slate-400">—</span>
          ) : (
            c.links.map((l) => (
              <span
                key={l.id}
                className={cn(
                  "rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700",
                  l.is_primary && "ring-1 ring-emerald-400",
                )}
              >
                #{l.company_id}
              </span>
            ))
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: t("xc.status", "Status"),
      render: (c) =>
        c.blocked ? (
          <span
            className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] font-medium text-rose-800"
            title={c.blocked_reason ?? ""}
          >
            {t("xc.blocked", "blocked")}
          </span>
        ) : (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-medium text-emerald-800">
            {t("status.active")}
          </span>
        ),
    },
  ];

  return (
    <Sheet
      title={t("xc.customers.title", "Cross-company customers")}
      subtitle={t(
        "xc.customers.subtitle",
        "One profile per buyer — credit and LTV consolidated across every company they purchase from",
      )}
    >
      <SearchBar
        value={search}
        onChange={setSearch}
      />

      <ListView
        rows={filtered}
        columns={columns}
        loading={customers.isLoading}
        rowKey={(c) => c.id}
      />
    </Sheet>
  );
}
