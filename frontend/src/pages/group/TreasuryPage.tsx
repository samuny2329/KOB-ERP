/** Treasury dashboard — bank accounts + cash pools + forecast risk. */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { Sheet, ViewSwitcher } from "@/components/views";
import { groupApi } from "@/lib/group";
import { cn } from "@/lib/utils";
import { useState } from "react";

const RISK_TONES = {
  ok: "bg-emerald-50 text-emerald-900 border-emerald-200",
  low: "bg-amber-50 text-amber-900 border-amber-200",
  critical: "bg-rose-50 text-rose-900 border-rose-200",
} as const;

const ACCOUNT_TYPE_BADGE: Record<string, string> = {
  checking: "bg-sky-100 text-sky-800",
  savings: "bg-emerald-100 text-emerald-800",
  fixed: "bg-violet-100 text-violet-800",
  credit_line: "bg-rose-100 text-rose-800",
  petty_cash: "bg-slate-100 text-slate-700",
};

export default function TreasuryPage() {
  const { t } = useTranslation();
  const [view, setView] = useState<"list" | "kanban">("list");
  const accounts = useQuery({
    queryKey: ["bank-accounts"],
    queryFn: () => groupApi.bankAccounts(),
  });
  const pools = useQuery({ queryKey: ["cash-pools"], queryFn: groupApi.cashPools });
  const forecasts = useQuery({
    queryKey: ["cash-forecasts"],
    queryFn: () => groupApi.cashForecasts(),
  });

  const groupTotal = (accounts.data ?? []).reduce((s, a) => s + a.current_balance, 0);
  const groupAvailable = (accounts.data ?? []).reduce(
    (s, a) => s + a.available_balance,
    0,
  );

  return (
    <Sheet
      title={t("treasury.title", "Treasury")}
      subtitle={t(
        "treasury.subtitle",
        "Bank accounts, cash pools, and risk-flagged forecasts across every company",
      )}
      actions={<ViewSwitcher value={view} onChange={setView} />}
    >
      {/* Group balance snapshot */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 p-5 text-white shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-400">
            {t("treasury.groupBalance", "Group balance")}
          </div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">
            ฿{groupTotal.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            ฿{groupAvailable.toLocaleString(undefined, { maximumFractionDigits: 0 })}{" "}
            {t("treasury.available", "available")}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            {t("treasury.accounts", "Bank accounts")}
          </div>
          <div className="mt-1 text-3xl font-semibold tabular-nums text-slate-900">
            {accounts.data?.length ?? "—"}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {t("treasury.acrossCompanies", "across companies")}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="text-xs font-medium uppercase tracking-wider text-slate-500">
            {t("treasury.pools", "Cash pools")}
          </div>
          <div className="mt-1 text-3xl font-semibold tabular-nums text-slate-900">
            {pools.data?.length ?? "—"}
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {(pools.data ?? []).reduce((s, p) => s + p.members.length, 0)}{" "}
            {t("treasury.totalMembers", "member accounts")}
          </div>
        </div>
      </div>

      {/* Forecast strip */}
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
          {t("treasury.forecastByCompany", "Forecast by company")}
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(forecasts.data ?? []).map((f) => (
            <div
              key={f.id}
              className={cn(
                "rounded-xl border p-4",
                RISK_TONES[f.risk_flag],
              )}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-xs uppercase tracking-wider opacity-80">
                    {t("treasury.company", "Company")} #{f.company_id}
                  </div>
                  <div className="text-base font-semibold">
                    {f.forecast_date} · +{f.horizon_days}d
                  </div>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                    f.risk_flag === "critical"
                      ? "bg-rose-600 text-white"
                      : f.risk_flag === "low"
                        ? "bg-amber-500 text-white"
                        : "bg-emerald-500 text-white",
                  )}
                >
                  {f.risk_flag}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                <div>
                  <div className="opacity-70">In</div>
                  <div className="font-semibold tabular-nums">
                    ฿{f.cash_in.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="opacity-70">Out</div>
                  <div className="font-semibold tabular-nums">
                    ฿{f.cash_out.toLocaleString()}
                  </div>
                </div>
                <div>
                  <div className="opacity-70">End</div>
                  <div className="font-semibold tabular-nums">
                    ฿{f.projected_balance.toLocaleString()}
                  </div>
                </div>
              </div>
            </div>
          ))}
          {forecasts.data?.length === 0 && (
            <div className="col-span-full rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-400">
              {t("treasury.noForecast", "No forecast snapshots yet")}
            </div>
          )}
        </div>
      </section>

      {/* Bank accounts list */}
      <section className="mt-8">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
          {t("treasury.accountList", "Bank accounts")}
        </h2>
        {view === "list" ? (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <table className="min-w-full divide-y divide-slate-200">
              <thead className="bg-slate-50/80 text-left text-[11px] font-medium uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Bank</th>
                  <th className="px-4 py-2.5">Account</th>
                  <th className="px-4 py-2.5">Type</th>
                  <th className="px-4 py-2.5">Co.</th>
                  <th className="px-4 py-2.5 text-right">Current</th>
                  <th className="px-4 py-2.5 text-right">Available</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-sm">
                {accounts.data?.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                      {t("status.empty")}
                    </td>
                  </tr>
                )}
                {accounts.data?.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-slate-900">{a.bank_name}</div>
                      {a.branch && (
                        <div className="text-xs text-slate-500">{a.branch}</div>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="font-mono text-xs">{a.account_number}</div>
                      <div className="text-xs text-slate-500">{a.account_name}</div>
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium",
                          ACCOUNT_TYPE_BADGE[a.account_type] ??
                            "bg-slate-100 text-slate-700",
                        )}
                      >
                        {a.account_type}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-600">
                      #{a.company_id}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums">
                      ฿{a.current_balance.toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-slate-600">
                      ฿{a.available_balance.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {accounts.data?.map((a) => (
              <div
                key={a.id}
                className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm font-semibold text-slate-900">
                      {a.bank_name}
                    </div>
                    <div className="font-mono text-xs text-slate-500">
                      {a.account_number}
                    </div>
                  </div>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-medium",
                      ACCOUNT_TYPE_BADGE[a.account_type] ?? "bg-slate-100 text-slate-700",
                    )}
                  >
                    {a.account_type}
                  </span>
                </div>
                <div className="mt-3 text-2xl font-semibold tabular-nums">
                  ฿{a.current_balance.toLocaleString()}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  ฿{a.available_balance.toLocaleString()} {t("treasury.available")}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </Sheet>
  );
}
