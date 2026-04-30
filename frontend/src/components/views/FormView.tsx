/** Form scaffold — page-level statusbar + content slot + save/discard footer.
 *
 * The form itself is whatever JSX you put inside (typically `<FieldGroup>`s),
 * keeping this component dumb about which fields a record has.
 */

import type { FormEvent, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

interface FormViewProps {
  children: ReactNode;
  statusBar?: ReactNode;
  onSubmit: () => void | Promise<void>;
  onDiscard?: () => void;
  saving?: boolean;
  dirty?: boolean;
  error?: string;
  saveLabel?: string;
}

export function FormView({
  children,
  statusBar,
  onSubmit,
  onDiscard,
  saving = false,
  dirty = false,
  error,
  saveLabel,
}: FormViewProps) {
  const { t } = useTranslation();
  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    void onSubmit();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {statusBar && (
        <div className="rounded-lg border border-slate-200 bg-white px-4 py-2 shadow-sm">
          {statusBar}
        </div>
      )}

      {children}

      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="sticky bottom-0 z-10 -mx-2 flex items-center justify-end gap-2 rounded-md border border-slate-200 bg-white/90 px-3 py-2 shadow-sm backdrop-blur">
        {onDiscard && (
          <button
            type="button"
            onClick={onDiscard}
            disabled={!dirty || saving}
            className={cn(
              "rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {t("action.discard")}
          </button>
        )}
        <button
          type="submit"
          disabled={!dirty || saving}
          className={cn(
            "rounded-md bg-brand-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-700",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          {saving ? t("status.loading") : (saveLabel ?? t("action.save"))}
        </button>
      </div>
    </form>
  );
}

interface ModalShellProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  size?: "sm" | "md" | "lg";
}

export function Modal({ open, onClose, title, children, size = "md" }: ModalShellProps) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className={cn(
          "max-h-[90vh] w-full overflow-auto rounded-2xl bg-white p-5 shadow-xl",
          size === "sm" && "max-w-md",
          size === "md" && "max-w-2xl",
          size === "lg" && "max-w-4xl",
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
