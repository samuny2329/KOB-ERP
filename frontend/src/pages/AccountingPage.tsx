import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { StateBadge } from "@/components/StateBadge";

interface Account {
  id: number;
  code: string;
  name: string;
  account_type: string;
  active: boolean;
}

interface JournalEntry {
  id: number;
  number: string;
  journal_id: number;
  state: string;
  entry_date: string;
  reference: string | null;
  memo: string | null;
}

interface Journal {
  id: number;
  code: string;
  name: string;
  journal_type: string;
}

const TYPE_COLORS: Record<string, string> = {
  asset: "bg-blue-100 text-blue-700",
  liability: "bg-red-100 text-red-700",
  equity: "bg-purple-100 text-purple-700",
  revenue: "bg-green-100 text-green-700",
  expense: "bg-orange-100 text-orange-700",
  cogs: "bg-amber-100 text-amber-700",
};

export default function AccountingPage() {
  const { data: accounts = [], isLoading: accsLoading } = useQuery<Account[]>({
    queryKey: ["accounts"],
    queryFn: () => api.get("/api/v1/accounting/accounts").then((r) => r.data),
  });

  const { data: journals = [] } = useQuery<Journal[]>({
    queryKey: ["journals"],
    queryFn: () => api.get("/api/v1/accounting/journals").then((r) => r.data),
  });

  const { data: entries = [], isLoading: entriesLoading } = useQuery<JournalEntry[]>({
    queryKey: ["journal-entries"],
    queryFn: () => api.get("/api/v1/accounting/entries").then((r) => r.data),
  });

  const journalMap = Object.fromEntries(journals.map((j) => [j.id, j.name]));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Accounting</h1>
        <p className="text-sm text-slate-500">
          {accounts.length} accounts · {journals.length} journals · {entries.length} entries
        </p>
      </div>

      {/* Chart of Accounts */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Chart of Accounts</h2>
        {accsLoading ? (
          <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />)}</div>
        ) : accounts.length === 0 ? (
          <p className="text-sm text-slate-400">No accounts yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Code</th>
                  <th className="px-4 py-2 text-left">Name</th>
                  <th className="px-4 py-2 text-left">Type</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {accounts.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-mono text-xs text-slate-600">{a.code}</td>
                    <td className="px-4 py-2">{a.name}</td>
                    <td className="px-4 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_COLORS[a.account_type] ?? "bg-slate-100 text-slate-600"}`}>
                        {a.account_type}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Journal Entries */}
      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-700 uppercase tracking-wider">Journal Entries</h2>
        {entriesLoading ? (
          <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-10 animate-pulse rounded bg-slate-100" />)}</div>
        ) : entries.length === 0 ? (
          <p className="text-sm text-slate-400">No journal entries yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">Number</th>
                  <th className="px-4 py-2 text-left">Journal</th>
                  <th className="px-4 py-2 text-left">Date</th>
                  <th className="px-4 py-2 text-left">Memo</th>
                  <th className="px-4 py-2 text-left">State</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {entries.map((e) => (
                  <tr key={e.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2 font-mono text-xs">{e.number}</td>
                    <td className="px-4 py-2 text-slate-600">{journalMap[e.journal_id] ?? "—"}</td>
                    <td className="px-4 py-2 text-slate-500">{e.entry_date}</td>
                    <td className="px-4 py-2 truncate max-w-xs text-slate-500">{e.memo ?? "—"}</td>
                    <td className="px-4 py-2"><StateBadge state={e.state} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
