/** Users module — Odoo-style List + Kanban + Form views, KOB-styled.
 *
 * Demonstrates the customview library on a real domain object: list with
 * filters/search, kanban toggle, and a form modal for create.
 */

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";

import {
  type Column,
  FieldChar,
  FieldBoolean,
  FieldGroup,
  FieldMany2many,
  FieldSelection,
  FormView,
  KanbanView,
  ListView,
  Modal,
  SearchBar,
  Sheet,
  ViewSwitcher,
  type ViewMode,
} from "@/components/views";
import type { UserRead } from "@/lib/api";
import { companiesApi, usersApi, type UserCreatePayload } from "@/lib/users";

interface DraftUser {
  email: string;
  full_name: string;
  password: string;
  is_superuser: boolean;
  preferred_locale: string;
  default_company_id: number | null;
  company_ids: number[];
}

const EMPTY_DRAFT: DraftUser = {
  email: "",
  full_name: "",
  password: "",
  is_superuser: false,
  preferred_locale: "th-TH",
  default_company_id: null,
  company_ids: [],
};

const FILTERS = [
  { key: "active", labelKey: "filter.active" },
  { key: "superusers", labelKey: "filter.superusers" },
] as const;

export default function UsersPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();

  const [view, setView] = useState<ViewMode>("list");
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Set<string>>(new Set(["active"]));
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DraftUser>(EMPTY_DRAFT);
  const [error, setError] = useState<string | null>(null);

  const usersQ = useQuery({ queryKey: ["users"], queryFn: usersApi.list });
  const companiesQ = useQuery({ queryKey: ["companies"], queryFn: companiesApi.list });

  const filteredRows = useMemo(() => {
    if (!usersQ.data) return [];
    return usersQ.data.filter((u) => {
      if (filters.has("active") && !u.is_active) return false;
      if (filters.has("superusers") && !u.is_superuser) return false;
      if (search) {
        const haystack = `${u.email} ${u.full_name}`.toLowerCase();
        if (!haystack.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [usersQ.data, filters, search]);

  const createMut = useMutation({
    mutationFn: (body: UserCreatePayload) => usersApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success(t("status.saved"));
      setOpen(false);
      setDraft(EMPTY_DRAFT);
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : t("status.error"));
    },
  });

  function toggleFilter(key: string) {
    setFilters((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function handleSubmit() {
    setError(null);
    createMut.mutate({
      email: draft.email,
      password: draft.password,
      full_name: draft.full_name,
      is_superuser: draft.is_superuser,
      default_company_id: draft.default_company_id ?? undefined,
      company_ids: draft.company_ids,
    });
  }

  const columns: Column<UserRead>[] = [
    {
      key: "name",
      header: t("users.fullName"),
      render: (u) => (
        <div>
          <div className="font-medium text-slate-900">{u.full_name}</div>
          <div className="text-xs text-slate-500">{u.email}</div>
        </div>
      ),
    },
    {
      key: "role",
      header: t("users.isSuperuser"),
      render: (u) =>
        u.is_superuser ? (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
            {t("users.isSuperuser")}
          </span>
        ) : (
          <span className="text-xs text-slate-500">—</span>
        ),
    },
    {
      key: "default_company",
      header: t("users.defaultCompany"),
      render: (u) => u.default_company?.name ?? <span className="text-slate-400">—</span>,
    },
    {
      key: "companies",
      header: t("users.companies"),
      render: (u) =>
        u.companies.length === 0 ? (
          <span className="text-slate-400">—</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {u.companies.map((c) => (
              <span
                key={c.id}
                className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700"
              >
                {c.code}
              </span>
            ))}
          </div>
        ),
    },
    {
      key: "locale",
      header: t("users.locale"),
      className: "text-slate-500",
      render: (u) => u.preferred_locale,
    },
    {
      key: "last_login",
      header: t("users.lastLogin"),
      className: "text-slate-500",
      render: (u) =>
        u.last_login_at ? new Date(u.last_login_at).toLocaleString() : t("date.never"),
    },
  ];

  return (
    <Sheet
      title={t("users.title")}
      subtitle={t("users.subtitle")}
      actions={
        <button
          type="button"
          onClick={() => {
            setDraft(EMPTY_DRAFT);
            setError(null);
            setOpen(true);
          }}
          className="rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700"
        >
          + {t("users.newUser")}
        </button>
      }
    >
      <SearchBar
        value={search}
        onChange={setSearch}
        filters={FILTERS.map((f) => ({ key: f.key, label: t(f.labelKey) }))}
        activeFilters={filters}
        onToggleFilter={toggleFilter}
        rightSlot={<ViewSwitcher value={view} onChange={setView} />}
      />

      {view === "list" ? (
        <ListView
          rows={filteredRows}
          columns={columns}
          loading={usersQ.isLoading}
          rowKey={(u) => u.id}
        />
      ) : (
        <KanbanView
          rows={filteredRows}
          loading={usersQ.isLoading}
          rowKey={(u) => u.id}
          renderCard={(u) => (
            <div>
              <div className="flex items-center gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
                  {u.full_name.slice(0, 2).toUpperCase()}
                </div>
                <div className="min-w-0">
                  <div className="truncate font-medium text-slate-900">{u.full_name}</div>
                  <div className="truncate text-xs text-slate-500">{u.email}</div>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                {u.is_superuser && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-amber-800">
                    {t("users.isSuperuser")}
                  </span>
                )}
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-700">
                  {u.preferred_locale}
                </span>
                {u.companies.map((c) => (
                  <span
                    key={c.id}
                    className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700"
                  >
                    {c.code}
                  </span>
                ))}
              </div>
            </div>
          )}
        />
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={t("users.newUser")}
        size="lg"
      >
        <FormView
          dirty={draft.email.length > 0 || draft.full_name.length > 0}
          saving={createMut.isPending}
          onSubmit={handleSubmit}
          onDiscard={() => {
            setDraft(EMPTY_DRAFT);
            setError(null);
          }}
          error={error ?? undefined}
        >
          <FieldGroup title={t("section.identity")}>
            <FieldChar
              label={t("users.fullName")}
              required
              value={draft.full_name}
              onChange={(v) => setDraft({ ...draft, full_name: v })}
            />
            <FieldChar
              label={t("users.email")}
              type="email"
              required
              value={draft.email}
              onChange={(v) => setDraft({ ...draft, email: v })}
            />
            <FieldChar
              label={t("users.password")}
              type="password"
              required
              value={draft.password}
              onChange={(v) => setDraft({ ...draft, password: v })}
              helper="≥ 8 ตัวอักษร"
              span={2}
            />
          </FieldGroup>

          <FieldGroup title={t("section.access")}>
            <FieldBoolean
              label={t("users.isSuperuser")}
              value={draft.is_superuser}
              onChange={(v) => setDraft({ ...draft, is_superuser: v })}
              helper="ข้ามการตรวจสอบสิทธิ์ทั้งหมด"
            />
            <FieldSelection
              label={t("users.defaultCompany")}
              value={String(draft.default_company_id ?? "")}
              onChange={(v) =>
                setDraft({
                  ...draft,
                  default_company_id: v ? Number(v) : null,
                })
              }
              options={[
                { value: "", label: "—" },
                ...(companiesQ.data ?? []).map((c) => ({
                  value: String(c.id),
                  label: `${c.code} · ${c.name}`,
                })),
              ]}
            />
            <FieldMany2many
              label={t("users.companies")}
              options={companiesQ.data ?? []}
              value={draft.company_ids}
              onChange={(v) => setDraft({ ...draft, company_ids: v })}
              optionId={(c) => c.id}
              optionLabel={(c) => `${c.code} · ${c.name}`}
            />
          </FieldGroup>

          <FieldGroup title={t("section.preferences")}>
            <FieldSelection
              label={t("users.locale")}
              value={draft.preferred_locale}
              onChange={(v) => setDraft({ ...draft, preferred_locale: v })}
              options={[
                { value: "th-TH", label: "ไทย" },
                { value: "en-US", label: "English" },
              ]}
            />
          </FieldGroup>
        </FormView>
      </Modal>
    </Sheet>
  );
}
