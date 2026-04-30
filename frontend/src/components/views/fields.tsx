/** Reusable form field components — Char, Email, Boolean, Selection, Many2many.
 *
 * The pattern mirrors Odoo: each field knows how to render its label + input
 * + helper text + invalid state, and reads/writes a single key on a record
 * passed in via props.  The form view binds them to a record with onChange
 * delegated up.
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface FieldShellProps {
  label: string;
  required?: boolean;
  helper?: string;
  error?: string;
  children: ReactNode;
  span?: 1 | 2;
}

export function FieldShell({ label, required, helper, error, children, span = 1 }: FieldShellProps) {
  return (
    <label
      className={cn(
        "block",
        span === 2 ? "sm:col-span-2" : "",
      )}
    >
      <span className="mb-1 block text-xs font-medium text-slate-700">
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </span>
      {children}
      {helper && !error && <span className="mt-1 block text-[11px] text-slate-500">{helper}</span>}
      {error && <span className="mt-1 block text-[11px] text-rose-600">{error}</span>}
    </label>
  );
}

interface FieldCharProps {
  label: string;
  value: string;
  onChange: (next: string) => void;
  type?: "text" | "email" | "password" | "url" | "tel";
  placeholder?: string;
  required?: boolean;
  readOnly?: boolean;
  helper?: string;
  error?: string;
  span?: 1 | 2;
}

export function FieldChar({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
  required,
  readOnly,
  helper,
  error,
  span,
}: FieldCharProps) {
  return (
    <FieldShell label={label} required={required} helper={helper} error={error} span={span}>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        readOnly={readOnly}
        required={required}
        className={cn(
          "block w-full rounded-md border bg-white px-3 py-1.5 text-sm shadow-sm",
          "focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500",
          error ? "border-rose-400" : "border-slate-300",
          readOnly && "cursor-not-allowed bg-slate-50 text-slate-500",
        )}
      />
    </FieldShell>
  );
}

interface FieldBooleanProps {
  label: string;
  value: boolean;
  onChange: (next: boolean) => void;
  helper?: string;
  span?: 1 | 2;
}

export function FieldBoolean({ label, value, onChange, helper, span }: FieldBooleanProps) {
  return (
    <FieldShell label={label} helper={helper} span={span}>
      <button
        type="button"
        role="switch"
        aria-checked={value}
        onClick={() => onChange(!value)}
        className={cn(
          "relative inline-flex h-6 w-11 items-center rounded-full transition",
          value ? "bg-brand-600" : "bg-slate-300",
        )}
      >
        <span
          className={cn(
            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition",
            value ? "translate-x-6" : "translate-x-1",
          )}
        />
      </button>
    </FieldShell>
  );
}

interface FieldSelectionOption {
  value: string;
  label: string;
}

interface FieldSelectionProps {
  label: string;
  value: string;
  onChange: (next: string) => void;
  options: FieldSelectionOption[];
  required?: boolean;
  helper?: string;
  error?: string;
  span?: 1 | 2;
}

export function FieldSelection({
  label,
  value,
  onChange,
  options,
  required,
  helper,
  error,
  span,
}: FieldSelectionProps) {
  return (
    <FieldShell label={label} required={required} helper={helper} error={error} span={span}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        className={cn(
          "block w-full rounded-md border bg-white px-3 py-1.5 text-sm shadow-sm",
          "focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500",
          error ? "border-rose-400" : "border-slate-300",
        )}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
}

interface FieldMany2manyProps<T> {
  label: string;
  options: T[];
  value: number[];
  onChange: (next: number[]) => void;
  optionId: (o: T) => number;
  optionLabel: (o: T) => string;
  helper?: string;
  span?: 1 | 2;
}

export function FieldMany2many<T>({
  label,
  options,
  value,
  onChange,
  optionId,
  optionLabel,
  helper,
  span = 2,
}: FieldMany2manyProps<T>) {
  const selected = new Set(value);
  function toggle(id: number) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(Array.from(next));
  }
  return (
    <FieldShell label={label} helper={helper} span={span}>
      <div className="flex flex-wrap gap-1.5">
        {options.length === 0 && <span className="text-xs text-slate-400">—</span>}
        {options.map((o) => {
          const id = optionId(o);
          const active = selected.has(id);
          return (
            <button
              key={id}
              type="button"
              onClick={() => toggle(id)}
              className={cn(
                "rounded-full border px-2.5 py-0.5 text-xs transition",
                active
                  ? "border-brand-500 bg-brand-50 text-brand-700"
                  : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50",
              )}
            >
              {optionLabel(o)}
            </button>
          );
        })}
      </div>
    </FieldShell>
  );
}

interface FieldGroupProps {
  title: string;
  children: ReactNode;
}

export function FieldGroup({ title, children }: FieldGroupProps) {
  return (
    <fieldset className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
        {title}
      </legend>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}
