/** Approvals — matrices per company + active substitutions. */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { Sheet } from "@/components/views";
import { groupApi } from "@/lib/group";

const DOC_LABELS: Record<string, string> = {
  purchase_order: "PO",
  sales_order: "SO",
  journal_entry: "JE",
  leave: "Leave",
  payslip: "Payslip",
  cost_allocation: "Cost alloc.",
  intercompany_loan: "ICO loan",
};

export default function ApprovalsPage() {
  const { t } = useTranslation();
  const matrices = useQuery({
    queryKey: ["approval-matrices"],
    queryFn: () => groupApi.approvalMatrices(),
  });
  const subs = useQuery({
    queryKey: ["approval-substitutions"],
    queryFn: () => groupApi.approvalSubstitutions(),
  });

  // Group matrices by company
  const byCompany: Record<number, typeof matrices.data> = {};
  for (const m of matrices.data ?? []) {
    (byCompany[m.company_id] ??= [] as never).push(m);
  }
  const companyIds = Object.keys(byCompany)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <Sheet
      title={t("approvals.title", "Approval rules")}
      subtitle={t(
        "approvals.subtitle",
        "Per-company matrix + cross-company fallback approvers when primary unavailable",
      )}
    >
      {/* Matrices grid */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
          {t("approvals.matricesHeader", "Approval matrices")}
        </h2>
        {matrices.isLoading && (
          <div className="rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-400">
            {t("status.loading")}
          </div>
        )}
        {matrices.data?.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 px-6 py-10 text-center text-sm text-slate-400">
            {t("approvals.noMatrices", "No approval matrices configured")}
          </div>
        )}
        <div className="space-y-6">
          {companyIds.map((cid) => {
            const items = byCompany[cid] ?? [];
            return (
              <div key={cid} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-slate-500">
                      {t("approvals.company", "Company")}
                    </div>
                    <div className="text-lg font-semibold text-slate-900">#{cid}</div>
                  </div>
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700">
                    {items.length} {t("approvals.documentTypes", "doc types")}
                  </span>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {items.map((m) => (
                    <div
                      key={m.id}
                      className="rounded-xl border border-slate-200 p-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px]">
                          {DOC_LABELS[m.document_type] ?? m.document_type}
                        </span>
                        {!m.active && (
                          <span className="text-[10px] uppercase text-slate-400">
                            inactive
                          </span>
                        )}
                      </div>
                      <table className="mt-2 w-full text-xs">
                        <thead className="text-left text-[10px] uppercase text-slate-400">
                          <tr>
                            <th className="py-1">Range</th>
                            <th className="py-1">Approver</th>
                            <th className="py-1 text-right">N</th>
                          </tr>
                        </thead>
                        <tbody>
                          {m.rules
                            .sort((a, b) => a.sequence - b.sequence)
                            .map((r) => (
                              <tr key={r.id} className="border-t border-slate-100">
                                <td className="py-1 tabular-nums">
                                  ≥ ฿{r.min_amount.toLocaleString()}
                                  {r.max_amount && ` < ฿${r.max_amount.toLocaleString()}`}
                                </td>
                                <td className="py-1">
                                  {r.approver_user_id
                                    ? `User #${r.approver_user_id}`
                                    : r.approver_group_id
                                      ? `Group #${r.approver_group_id}`
                                      : "—"}
                                </td>
                                <td className="py-1 text-right tabular-nums">
                                  {r.requires_n_approvers}
                                </td>
                              </tr>
                            ))}
                          {m.rules.length === 0 && (
                            <tr>
                              <td colSpan={3} className="py-2 text-center text-slate-400">
                                no rules
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Substitutions */}
      <section className="mt-10">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">
          {t("approvals.substitutions", "Active substitutions")}
        </h2>
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50/80 text-left text-[11px] font-medium uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-2.5">Primary</th>
                <th className="px-4 py-2.5">Fallback</th>
                <th className="px-4 py-2.5">Doc type</th>
                <th className="px-4 py-2.5">Window</th>
                <th className="px-4 py-2.5">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {subs.data?.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                    {t("approvals.noSubs", "No active substitutions")}
                  </td>
                </tr>
              )}
              {subs.data?.map((s) => (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2.5">
                    <div className="font-medium">User #{s.primary_user_id}</div>
                    {s.primary_company_id && (
                      <div className="text-xs text-slate-500">
                        Co. #{s.primary_company_id}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="font-medium text-emerald-700">
                      → User #{s.fallback_user_id}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    {s.document_type ? (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px]">
                        {DOC_LABELS[s.document_type] ?? s.document_type}
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">all docs</span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-600">
                    {s.valid_from} → {s.valid_to}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-600">
                    {s.reason ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </Sheet>
  );
}
