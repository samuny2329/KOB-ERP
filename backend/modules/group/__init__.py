"""Group / Multi-company management module — KOB-exclusive features.

Things this module does that no other ERP does (or does this directly):
  - GroupKpiSnapshot      — KPI rollup across the company hierarchy
  - InventoryPool / Rule  — virtual stock pool + routing across siblings
  - CostAllocation / Rule — shared expense splitting (rent, utilities, salaries)
  - InterCompanyLoan      — track inter-co payables w/ interest + reconcile
  - TaxGroup              — Thai VAT-group filing support
  - ApprovalMatrix / Rule — per-company approval routing matrix
  - CompanyComplianceItem — Thai compliance deadlines (PND/SSO/Audit) per company

The schema name in Postgres is ``grp`` (Postgres reserves ``group``).
"""
