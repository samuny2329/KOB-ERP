/** Header dropdown that switches the active company.
 *
 * Reads from the auth context's `user.companies`.  On select, calls
 * `/companies/{id}/switch` and refreshes the auth state.
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { companiesApi } from "@/lib/users";
import { cn } from "@/lib/utils";

export function CompanySwitcher() {
  const { user, refresh } = useAuth();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);

  const switchMut = useMutation({
    mutationFn: (id: number) => companiesApi.switch(id),
    onSuccess: async () => {
      await refresh();
      qc.invalidateQueries();
      toast.success(t("status.saved"));
      setOpen(false);
    },
    onError: () => toast.error(t("status.error")),
  });

  if (!user || (user.companies.length <= 1 && !user.is_superuser)) {
    if (!user?.default_company) return null;
    return (
      <span className="hidden whitespace-nowrap rounded-md bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700 sm:inline-block">
        {user.default_company.code}
      </span>
    );
  }

  const current = user.default_company;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50",
        )}
      >
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" />
        {current ? current.code : "—"}
        <svg
          className={cn("h-3 w-3 transition", open && "rotate-180")}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.06l3.71-3.83a.75.75 0 111.08 1.04l-4.25 4.39a.75.75 0 01-1.08 0L5.21 8.27a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      {open && (
        <div
          className="absolute right-0 z-40 mt-1 w-56 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg"
          onMouseLeave={() => setOpen(false)}
        >
          {user.companies.map((c) => {
            const isCurrent = current?.id === c.id;
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => switchMut.mutate(c.id)}
                disabled={switchMut.isPending}
                className={cn(
                  "flex w-full items-center justify-between px-3 py-2 text-xs hover:bg-slate-50",
                  isCurrent && "bg-brand-50 text-brand-700",
                )}
              >
                <div className="flex flex-col items-start">
                  <span className="font-mono text-[10px] uppercase tracking-wider opacity-70">
                    {c.code}
                  </span>
                  <span className="font-medium">{c.name}</span>
                </div>
                {isCurrent && <span className="text-brand-600">✓</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
