import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StateBadge } from "@/components/StateBadge";

interface Employee {
  id: number;
  employee_code: string;
  first_name: string;
  last_name: string;
  nick_name: string | null;
  department_id: number | null;
  job_title: string | null;
  hire_date: string | null;
  active: boolean;
}

interface Department {
  id: number;
  code: string;
  name: string;
}

interface Leave {
  id: number;
  employee_id: number;
  leave_type_id: number;
  state: string;
  date_from: string;
  date_to: string;
  days_requested: number;
}

export default function HRPage() {
  const { data: employees = [], isLoading: empLoading } = useQuery<Employee[]>({
    queryKey: ["employees"],
    queryFn: () => api.get("/api/v1/hr/employees").then((r) => r.data),
  });

  const { data: departments = [] } = useQuery<Department[]>({
    queryKey: ["departments"],
    queryFn: () => api.get("/api/v1/hr/departments").then((r) => r.data),
  });

  const { data: leaves = [] } = useQuery<Leave[]>({
    queryKey: ["leaves"],
    queryFn: () => api.get("/api/v1/hr/leaves").then((r) => r.data),
  });

  const deptMap = Object.fromEntries(departments.map((d) => [d.id, d.name]));
  const activeEmp = employees.filter((e) => e.active).length;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Human Resources</h1>
          <p className="text-sm text-slate-500">
            {departments.length} departments · {activeEmp} active employees
          </p>
        </div>
        <div className="flex gap-3">
          <div className="rounded-lg bg-pink-50 px-4 py-2 text-center">
            <div className="text-2xl font-bold text-pink-700">{activeEmp}</div>
            <div className="text-xs text-pink-500">Active Staff</div>
          </div>
          <div className="rounded-lg bg-amber-50 px-4 py-2 text-center">
            <div className="text-2xl font-bold text-amber-700">
              {leaves.filter((l) => l.state === "submitted").length}
            </div>
            <div className="text-xs text-amber-500">Pending Leaves</div>
          </div>
        </div>
      </div>

      {/* Departments */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Departments</h2>
        <div className="flex flex-wrap gap-2">
          {departments.map((d) => (
            <div key={d.id} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-sm">
              <span className="font-medium text-slate-900">{d.name}</span>
              <span className="ml-1 text-slate-400 text-xs">
                ({employees.filter((e) => e.department_id === d.id).length})
              </span>
            </div>
          ))}
          {departments.length === 0 && <p className="text-sm text-slate-400">No departments yet.</p>}
        </div>
      </section>

      {/* Employees */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Employees</h2>
        {empLoading ? (
          <div className="grid gap-3 sm:grid-cols-3">
            {[...Array(6)].map((_, i) => <div key={i} className="h-20 animate-pulse rounded-lg bg-slate-100" />)}
          </div>
        ) : employees.length === 0 ? (
          <p className="text-sm text-slate-400">No employees yet.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-3">
            {employees.map((e) => (
              <div key={e.id} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-center gap-3">
                  <div className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-pink-100 text-sm font-bold text-pink-600">
                    {e.first_name[0]}{e.last_name[0]}
                  </div>
                  <div>
                    <div className="font-medium text-slate-900">
                      {e.first_name} {e.last_name}
                      {e.nick_name && <span className="ml-1 text-slate-400 text-xs">({e.nick_name})</span>}
                    </div>
                    <div className="text-xs text-slate-400">
                      {e.job_title ?? "—"} · {deptMap[e.department_id!] ?? "—"}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Leaves */}
      {leaves.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Recent Leaves</h2>
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Employee</th>
                  <th className="px-4 py-2 text-left">From</th>
                  <th className="px-4 py-2 text-left">To</th>
                  <th className="px-4 py-2 text-right">Days</th>
                  <th className="px-4 py-2 text-left">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {leaves.slice(0, 10).map((l) => {
                  const emp = employees.find((e) => e.id === l.employee_id);
                  return (
                    <tr key={l.id} className="hover:bg-slate-50">
                      <td className="px-4 py-2">
                        {emp ? `${emp.first_name} ${emp.last_name}` : `#${l.employee_id}`}
                      </td>
                      <td className="px-4 py-2 text-slate-500">{l.date_from}</td>
                      <td className="px-4 py-2 text-slate-500">{l.date_to}</td>
                      <td className="px-4 py-2 text-right">{l.days_requested}</td>
                      <td className="px-4 py-2"><StateBadge state={l.state} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
