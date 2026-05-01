/** Compliance calendar — Thai filings (PND/SSO/Audit) per company. */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { SearchBar, type FilterChip, Sheet } from "@/components/views";
import { groupApi, type ComplianceItem, type ComplianceState } from "@/lib/group";
import { cn } from "@/lib/utils";

const STATE_TONES: Record<ComplianceState, string> = {
  pending: "bg-slate-100 text-slate-700",
  in_progress: "bg-sky-100 text-sky-800",
  submitted: "bg-emerald-100 text-emerald-800",
  overdue: "bg-rose-100 text-rose-800",
  cancelled: "bg-slate-200 text-slate-500",
};

const TYPE_LABELS: Record<string, string> = {
  vat_pp30: "VAT pp.30",
  wht_pnd1: "WHT ภงด.1",
  wht_pnd3: "WHT ภงด.3",
  wht_pnd53: "WHT ภงด.53",
  social_security: "SSO",
  annual_audit: "Annual audit",
  corporate_pnd50: "CIT ภงด.50",
  half_year_pnd51: "Mid-year ภงด.51",
  trademark_renewal: "Trademark",
  license_renewal: "License",
  other: "Other",
};

function daysUntil(due: string): number {
  const d = new Date(due);
  const now = new Date();
  return Math.floor((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

export default function CompliancePage() {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Set<string>>(new Set(["upcoming"]));
  const items = useQuery({
    queryKey: ["compliance-items"],
    queryFn: () => groupApi.complianceItems(),
  });

  const all = items.data ?? [];
  const filtered = all.filter((i) => {
    const days = daysUntil(i.due_date);
    if (filters.has("upcoming") && (days < 0 || days > 14)) return false;
    if (filters.has("overdue") && days >= 0) return false;
    if (filters.has("submitted") && i.state !== "submitted") return false;
    if (
      search &&
      !`${i.compliance_type} ${i.period_label} ${i.reference_number ?? ""}`
        .toLowerCase()
        .includes(search.toLowerCase())
    ) {
      return false;
    }
    return true;
  });

  function toggleFilter(key: string) {
    setFilters((s) => {
      const next = new Set(s);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const filterChips: FilterChip[] = [
    { key: "upcoming", label: t("compliance.upcoming", "Next 14 days") },
    { key: "overdue", label: t("compliance.overdue", "Overdue") },
    { key: "submitted", label: t("compliance.submitted", "Submitted") },
  ];

  // Group by month for the calendar view
  const byMonth: Record<string, ComplianceItem[]> = {};
  for (const item of filtered) {
    const ym = item.due_date.slice(0, 7);
    (byMonth[ym] ??= []).push(item);
  }
  const sortedMonths = Object.keys(byMonth).sort();

  // Counts for header strip
  const overdueCount = all.filter((i) => daysUntil(i.due_date) < 0 && i.state !== "submitted")
    .length;
  const dueSoon = all.filter(
    (i) => {
      const d = daysUntil(i.due_date);
      return d >= 0 && d <= 14 && i.state !== "submitted";
    },
  ).length;
  const submitted = all.filter((i) => i.state === "submitted").length;

  return (
    <Sheet
      title={t("compliance.title", "Compliance calendar")}
      subtitle={t(
        "compliance.subtitle",
        "Thai regulatory filings — VAT, WHT, SSO, audit, license renewal — tracked per company",
      )}
    >
      {/* Header strip */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
          <div className="text-xs uppercase tracking-wider text-rose-700">
            {t("compliance.overdueShort", "Overdue")}
          </div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-rose-900">
            {overdueCount}
          </div>
        </div>
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <div className="text-xs uppercase tracking-wider text-amber-700">
            {t("compliance.dueSoon", "Due in 14 days")}
          </div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-amber-900">
            {dueSoon}
          </div>
        </div>
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <div className="text-xs uppercase tracking-wider text-emerald-700">
            {t("compliance.submittedShort", "Submitted")}
          </div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-emerald-900">
            {submitted}
          </div>
        </div>
      </div>

      <SearchBar
        value={search}
        onChange={setSearch}
        filters={filterChips}
        activeFilters={filters}
        onToggleFilter={toggleFilter}
      />

      {/* Month-grouped accordion */}
      <div className="space-y-6">
        {sortedMonths.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-sm text-slate-400">
            {t("status.empty")}
          </div>
        )}
        {sortedMonths.map((ym) => {
          const date = new Date(ym + "-01");
          const monthLabel = date.toLocaleDateString(undefined, {
            month: "long",
            year: "numeric",
          });
          return (
            <div key={ym}>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-500">
                {monthLabel}
              </h3>
              <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <table className="min-w-full divide-y divide-slate-200">
                  <thead className="bg-slate-50/80 text-left text-[11px] font-medium uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-4 py-2.5">Type</th>
                      <th className="px-4 py-2.5">Period</th>
                      <th className="px-4 py-2.5">Co.</th>
                      <th className="px-4 py-2.5">State</th>
                      <th className="px-4 py-2.5 text-right">Due</th>
                      <th className="px-4 py-2.5 text-right">Days</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-sm">
                    {byMonth[ym]
                      .sort((a, b) => a.due_date.localeCompare(b.due_date))
                      .map((i) => {
                        const days = daysUntil(i.due_date);
                        const isOverdue = days < 0 && i.state !== "submitted";
                        return (
                          <tr
                            key={i.id}
                            className={cn(
                              "hover:bg-slate-50",
                              isOverdue && "bg-rose-50/50",
                            )}
                          >
                            <td className="px-4 py-2.5 font-medium">
                              {TYPE_LABELS[i.compliance_type] ?? i.compliance_type}
                            </td>
                            <td className="px-4 py-2.5 text-slate-600">
                              {i.period_label}
                            </td>
                            <td className="px-4 py-2.5 text-xs text-slate-500">
                              #{i.company_id}
                            </td>
                            <td className="px-4 py-2.5">
                              <span
                                className={cn(
                                  "rounded-full px-2 py-0.5 text-[11px] font-medium",
                                  STATE_TONES[i.state],
                                )}
                              >
                                {i.state}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-right tabular-nums">
                              {i.due_date}
                            </td>
                            <td
                              className={cn(
                                "px-4 py-2.5 text-right tabular-nums font-medium",
                                isOverdue
                                  ? "text-rose-700"
                                  : days <= 7
                                    ? "text-amber-700"
                                    : "text-slate-600",
                              )}
                            >
                              {isOverdue ? `${Math.abs(days)}d ago` : `${days}d`}
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              </div>
            </div>
          );
        })}
      </div>
    </Sheet>
  );
}
