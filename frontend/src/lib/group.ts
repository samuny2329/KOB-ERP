/** API types + client helpers for the group / multi-company module. */
import { api } from "@/lib/api";

// ── Group KPI ──────────────────────────────────────────────────────────

export type KpiMetric =
  | "revenue"
  | "gross_margin"
  | "fulfillment_sla_pct"
  | "pick_accuracy_pct"
  | "ar_days"
  | "ap_days"
  | "headcount"
  | "active_customers";

export interface GroupKpiSnapshot {
  id: number;
  company_id: number;
  metric: string;
  period_start: string;
  period_end: string;
  value: number;
  unit: string | null;
  refreshed_at: string;
}

export interface GroupKpiRollup {
  parent_company_id: number;
  metric: string;
  period_start: string;
  period_end: string;
  own_value: number;
  children_value: number;
  total_value: number;
  children_breakdown: Array<{
    company_id: number;
    code: string;
    name: string;
    value: number;
  }>;
}

// ── Cross-company partners ─────────────────────────────────────────────

export interface CrossCompanyCustomerLink {
  id: number;
  profile_id: number;
  company_id: number;
  local_customer_id: number;
  joined_at: string;
  is_primary: boolean;
}

export interface CrossCompanyCustomer {
  id: number;
  group_code: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  primary_email: string | null;
  primary_phone: string | null;
  customer_group: string;
  group_credit_limit: number;
  group_credit_consumed: number;
  group_ltv_score: number;
  blocked: boolean;
  blocked_reason: string | null;
  active: boolean;
  links: CrossCompanyCustomerLink[];
}

export interface CrossCompanyVendorLink {
  id: number;
  profile_id: number;
  company_id: number;
  local_vendor_id: number;
  is_primary: boolean;
}

export interface CrossCompanyVendor {
  id: number;
  group_code: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  payment_currency: string;
  lifetime_spend: number;
  ytd_spend: number;
  group_otd_pct: number;
  group_quality_pct: number;
  group_score: number;
  blocked: boolean;
  blocked_reason: string | null;
  active: boolean;
  links: CrossCompanyVendorLink[];
}

// ── Volume rebate ──────────────────────────────────────────────────────

export interface VolumeRebateTier {
  id: number;
  vendor_profile_id: number;
  period_kind: string;
  min_spend: number;
  max_spend: number | null;
  rebate_pct: number;
  active: boolean;
}

export interface VolumeRebateAccrual {
  id: number;
  vendor_profile_id: number;
  period_kind: string;
  period_start: string;
  period_end: string;
  total_group_spend: number;
  matched_tier_pct: number;
  accrued_rebate: number;
  settled_amount: number;
  settled_at: string | null;
}

// ── Treasury ───────────────────────────────────────────────────────────

export interface BankAccount {
  id: number;
  company_id: number;
  bank_name: string;
  branch: string | null;
  account_number: string;
  account_name: string;
  account_type: string;
  currency: string;
  current_balance: number;
  available_balance: number;
  last_reconciled_at: string | null;
  active: boolean;
}

export interface CashPoolMember {
  id: number;
  pool_id: number;
  bank_account_id: number;
  priority: number;
  min_balance: number;
}

export interface CashPool {
  id: number;
  code: string;
  name: string;
  parent_company_id: number;
  target_balance: number;
  currency: string;
  sweep_threshold_pct: number;
  active: boolean;
  members: CashPoolMember[];
}

export type CashRiskFlag = "ok" | "low" | "critical";

export interface CashForecastSnapshot {
  id: number;
  company_id: number;
  forecast_date: string;
  horizon_days: number;
  currency: string;
  opening_balance: number;
  cash_in: number;
  cash_out: number;
  projected_balance: number;
  risk_flag: CashRiskFlag;
}

// ── Compliance ─────────────────────────────────────────────────────────

export type ComplianceState =
  | "pending"
  | "in_progress"
  | "submitted"
  | "overdue"
  | "cancelled";

export interface ComplianceItem {
  id: number;
  company_id: number;
  compliance_type: string;
  period_label: string;
  state: ComplianceState;
  due_date: string;
  submitted_date: string | null;
  submitted_by: number | null;
  reference_number: string | null;
  amount_filed: number | null;
  note: string | null;
}

// ── Approvals ──────────────────────────────────────────────────────────

export type ApprovableDoc =
  | "purchase_order"
  | "sales_order"
  | "journal_entry"
  | "leave"
  | "payslip"
  | "cost_allocation"
  | "intercompany_loan";

export interface ApprovalMatrixRule {
  id: number;
  matrix_id: number;
  sequence: number;
  min_amount: number;
  max_amount: number | null;
  approver_user_id: number | null;
  approver_group_id: number | null;
  requires_n_approvers: number;
  active: boolean;
}

export interface ApprovalMatrix {
  id: number;
  company_id: number;
  document_type: string;
  note: string | null;
  active: boolean;
  rules: ApprovalMatrixRule[];
}

export interface ApprovalSubstitution {
  id: number;
  primary_user_id: number;
  fallback_user_id: number;
  primary_company_id: number | null;
  document_type: string | null;
  valid_from: string;
  valid_to: string;
  reason: string | null;
  active: boolean;
}

// ── Inventory pool ─────────────────────────────────────────────────────

export interface InventoryPool {
  id: number;
  code: string;
  name: string;
  parent_company_id: number;
  active: boolean;
}

export interface StockLookupOption {
  company_id: number;
  warehouse_id: number;
  available_qty: number;
  priority: number;
  estimated_cost: number;
  chosen: boolean;
}

// ── API ────────────────────────────────────────────────────────────────

export const groupApi = {
  // KPI
  kpiSnapshots: (params?: { company_id?: number; metric?: string }) =>
    api.get<GroupKpiSnapshot[]>("/group/kpi-snapshots", { params }).then((r) => r.data),
  kpiRollup: (params: {
    parent_company_id: number;
    metric: string;
    period_start: string;
    period_end: string;
  }) =>
    api.get<GroupKpiRollup>("/group/kpi-rollup", { params }).then((r) => r.data),

  // Customer / Vendor 360
  customers: () =>
    api.get<CrossCompanyCustomer[]>("/group/customers").then((r) => r.data),
  vendors: () =>
    api.get<CrossCompanyVendor[]>("/group/vendors").then((r) => r.data),

  // Volume rebate
  rebateTiers: (vendorProfileId?: number) =>
    api
      .get<VolumeRebateTier[]>("/group/rebate-tiers", {
        params: { vendor_profile_id: vendorProfileId },
      })
      .then((r) => r.data),
  rebateAccruals: (vendorProfileId?: number) =>
    api
      .get<VolumeRebateAccrual[]>("/group/rebate-accruals", {
        params: { vendor_profile_id: vendorProfileId },
      })
      .then((r) => r.data),

  // Treasury
  bankAccounts: (companyId?: number) =>
    api
      .get<BankAccount[]>("/group/bank-accounts", {
        params: { company_id: companyId },
      })
      .then((r) => r.data),
  cashPools: () =>
    api.get<CashPool[]>("/group/cash-pools").then((r) => r.data),
  cashForecasts: (params?: { company_id?: number; risk_flag?: string }) =>
    api.get<CashForecastSnapshot[]>("/group/cash-forecasts", { params }).then((r) => r.data),

  // Compliance
  complianceItems: (params?: {
    company_id?: number;
    state?: string;
    overdue_only?: boolean;
  }) =>
    api.get<ComplianceItem[]>("/group/compliance-items", { params }).then((r) => r.data),

  // Approvals
  approvalMatrices: (companyId?: number) =>
    api
      .get<ApprovalMatrix[]>("/group/approval-matrices", {
        params: { company_id: companyId },
      })
      .then((r) => r.data),
  approvalSubstitutions: (primaryUserId?: number) =>
    api
      .get<ApprovalSubstitution[]>("/group/approval-substitutions", {
        params: { primary_user_id: primaryUserId, active_only: true },
      })
      .then((r) => r.data),
  resolveApprover: (body: {
    user_id: number;
    on_date?: string;
    document_type?: string;
  }) =>
    api
      .post<{
        primary_user_id: number;
        effective_user_id: number;
        substituted: boolean;
        reason: string | null;
      }>("/group/approvers/resolve", body)
      .then((r) => r.data),

  // Inventory pool
  inventoryPools: () =>
    api.get<InventoryPool[]>("/group/inventory-pools").then((r) => r.data),
  poolLookup: (poolId: number, body: { product_id: number; qty: number }) =>
    api
      .post<StockLookupOption[]>(`/group/inventory-pools/${poolId}/lookup`, body)
      .then((r) => r.data),
};
