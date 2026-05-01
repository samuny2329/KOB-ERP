/** Group Hub — landing page for the multi-company module.
 *
 * Shows aggregated tiles for KPI rollup, treasury risk, compliance status,
 * top customers/vendors.  Each tile clicks through to its own page.
 */

import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Sheet } from "@/components/views";
import { groupApi } from "@/lib/group";
import { cn } from "@/lib/utils";

interface MetricTileProps {
  label: string;
  primary: string | number;
  secondary?: string;
  href?: string;
  tone?: "ok" | "warn" | "alert" | "neutral";
}

function MetricTile({ label, primary, secondary, href, tone = "neutral" }: MetricTileProps) {
  const navigate = useNavigate();
  const tones = {
    ok: "from-emerald-500 to-emerald-600 text-emerald-50",
    warn: "from-amber-500 to-orange-500 text-amber-50",
    alert: "from-rose-500 to-rose-600 text-rose-50",
    neutral: "from-slate-700 to-slate-800 text-slate-100",
  } as const;
  return (
    <button
      type="button"
      onClick={() => href && navigate(href)}
      disabled={!href}
      className={cn(
        "rounded-2xl bg-gradient-to-br p-5 text-left shadow-sm transition",
        tones[tone],
        href ? "hover:-translate-y-0.5 hover:shadow-md cursor-pointer" : "cursor-default",
      )}
    >
      <div className="text-xs font-medium uppercase tracking-wider opacity-80">{label}</div>
      <div className="mt-1 text-3xl font-semibold leading-none tabular-nums">{primary}</div>
      {secondary && <div className="mt-1 text-xs opacity-80">{secondary}</div>}
    </button>
  );
}

export default function GroupHubPage() {
  const { t } = useTranslation();
  const customers = useQuery({ queryKey: ["xc-customers"], queryFn: groupApi.customers });
  const vendors = useQuery({ queryKey: ["xc-vendors"], queryFn: groupApi.vendors });
  const compliance = useQuery({
    queryKey: ["compliance-items", "overdue"],
    queryFn: () => groupApi.complianceItems({ overdue_only: true }),
  });
  const cash = useQuery({
    queryKey: ["cash-forecasts"],
    queryFn: () => groupApi.cashForecasts(),
  });
  const accruals = useQuery({
    queryKey: ["rebate-accruals"],
    queryFn: () => groupApi.rebateAccruals(),
  });

  const overdueCount = compliance.data?.length ?? 0;
  const criticalCash = (cash.data ?? []).filter((c) => c.risk_flag === "critical").length;
  const lowCash = (cash.data ?? []).filter((c) => c.risk_flag === "low").length;
  const totalAccrued = (accruals.data ?? []).reduce(
    (sum, a) => sum + (a.accrued_rebate || 0),
    0,
  );

  return (
    <Sheet
      title={t("group.hub.title", "Group Hub")}
      subtitle={t(
        "group.hub.subtitle",
        "Multi-company command centre — KPIs, compliance, treasury, partners",
      )}
    >
      {/* Top metrics */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricTile
          label={t("group.hub.customers", "Group customers")}
          primary={customers.data?.length ?? "—"}
          secondary={t("group.hub.linkedToCompanies", "linked across companies")}
          href="/group/customers"
        />
        <MetricTile
          label={t("group.hub.vendors", "Group vendors")}
          primary={vendors.data?.length ?? "—"}
          secondary={t("group.hub.tracked", "tracked")}
          href="/group/vendors"
        />
        <MetricTile
          label={t("group.hub.compliance", "Compliance overdue")}
          primary={overdueCount}
          secondary={t("group.hub.openFilings", "open filings")}
          tone={overdueCount > 0 ? "alert" : "ok"}
          href="/group/compliance"
        />
        <MetricTile
          label={t("group.hub.cash", "Cash risk")}
          primary={criticalCash > 0 ? `${criticalCash} 🔴` : lowCash > 0 ? `${lowCash} 🟡` : "✓"}
          secondary={
            criticalCash > 0
              ? t("group.hub.critical", "critical")
              : lowCash > 0
                ? t("group.hub.low", "watching")
                : t("group.hub.ok", "all healthy")
          }
          tone={criticalCash > 0 ? "alert" : lowCash > 0 ? "warn" : "ok"}
          href="/group/treasury"
        />
      </div>

      {/* Secondary metrics */}
      <div className="mt-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            {t("group.hub.topRebates", "Top rebate accruals (this period)")}
          </h2>
          <div className="mt-3 space-y-2">
            {(accruals.data ?? []).slice(0, 5).map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2"
              >
                <div>
                  <div className="text-sm font-medium">Vendor #{a.vendor_profile_id}</div>
                  <div className="text-xs text-slate-500">
                    {a.period_kind} · {a.period_start} → {a.period_end}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-base font-semibold tabular-nums">
                    ฿{a.accrued_rebate.toLocaleString()}
                  </div>
                  <div className="text-xs text-slate-500">
                    @ {a.matched_tier_pct.toFixed(2)}%
                  </div>
                </div>
              </div>
            ))}
            {accruals.data?.length === 0 && (
              <div className="rounded-lg border border-dashed border-slate-300 px-3 py-6 text-center text-sm text-slate-400">
                {t("status.empty")}
              </div>
            )}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-slate-200 pt-3">
            <span className="text-sm text-slate-500">
              {t("group.hub.totalAccrued", "Total accrued")}
            </span>
            <span className="text-base font-semibold tabular-nums">
              ฿{totalAccrued.toLocaleString()}
            </span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            {t("group.hub.overdueCompliance", "Overdue compliance")}
          </h2>
          <div className="mt-3 space-y-2">
            {(compliance.data ?? []).slice(0, 5).map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between rounded-lg bg-rose-50 px-3 py-2"
              >
                <div>
                  <div className="text-sm font-medium text-rose-900">{c.compliance_type}</div>
                  <div className="text-xs text-rose-700">
                    Co. #{c.company_id} · {c.period_label}
                  </div>
                </div>
                <div className="text-right text-xs">
                  <div className="font-semibold text-rose-700">{c.due_date}</div>
                  <div className="text-rose-600">{c.state}</div>
                </div>
              </div>
            ))}
            {compliance.data?.length === 0 && (
              <div className="rounded-lg border border-dashed border-emerald-300 bg-emerald-50 px-3 py-6 text-center text-sm text-emerald-700">
                ✓ {t("group.hub.allCurrent", "All filings current")}
              </div>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">
            {t("group.hub.cashForecast", "Cash forecast risk")}
          </h2>
          <div className="mt-3 space-y-2">
            {(cash.data ?? []).slice(0, 5).map((c) => {
              const tone =
                c.risk_flag === "critical"
                  ? "bg-rose-50 text-rose-900"
                  : c.risk_flag === "low"
                    ? "bg-amber-50 text-amber-900"
                    : "bg-emerald-50 text-emerald-900";
              return (
                <div
                  key={c.id}
                  className={cn("flex items-center justify-between rounded-lg px-3 py-2", tone)}
                >
                  <div>
                    <div className="text-sm font-medium">Company #{c.company_id}</div>
                    <div className="text-xs opacity-80">
                      {c.forecast_date} · +{c.horizon_days}d
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold tabular-nums">
                      ฿{c.projected_balance.toLocaleString()}
                    </div>
                    <div className="text-xs uppercase tracking-wider opacity-80">
                      {c.risk_flag}
                    </div>
                  </div>
                </div>
              );
            })}
            {cash.data?.length === 0 && (
              <div className="rounded-lg border border-dashed border-slate-300 px-3 py-6 text-center text-sm text-slate-400">
                {t("group.hub.noCashSnapshots", "No cash snapshots yet")}
              </div>
            )}
          </div>
        </div>
      </div>
    </Sheet>
  );
}
