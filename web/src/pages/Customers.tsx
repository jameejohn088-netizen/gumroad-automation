import { api } from '../api/client';
import { accountQuery, useApp } from '../context/AppContext';
import { usePaginated } from '../hooks/usePaginated';
import { formatDate, formatMoney } from '../utils';
import { EmptyState, ErrorBanner, Input, LoadingBlock, PageHeader, Pagination, TableShell, tdClass, thClass } from '../components/ui';

export default function Customers() {
  const { selectedAccountId } = useApp();
  const q0 = accountQuery(selectedAccountId).account_id;
  const { page, setPage, q, setQ, data, loading, error, reload, perPage } = usePaginated(api.customers, q0);

  return (
    <div>
      <PageHeader title="Customers" description="Derived from sales, deduplicated by email." />
      <div className="mb-4 max-w-sm">
        <label htmlFor="customer-search" className="sr-only">Search customers</label>
        <Input id="customer-search" placeholder="Search by email or name…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && !data && <LoadingBlock />}
      {error ? <ErrorBanner error={error} onRetry={reload} /> : null}

      {data && data.items.length === 0 && !loading && (
        <EmptyState title="No customers found" description={q ? 'Try a different search.' : 'Customers appear after syncing sales.'} />
      )}

      {data && data.items.length > 0 && (
        <>
          <TableShell>
            <thead className="bg-gray-50 dark:bg-gray-800/60">
              <tr>
                <th className={thClass}>Email</th>
                <th className={thClass}>Name</th>
                <th className={thClass}>First purchase</th>
                <th className={thClass}>Total spent</th>
                <th className={thClass}>Purchases</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              {data.items.map((c) => (
                <tr key={c.id}>
                  <td className={tdClass}>{c.email}</td>
                  <td className={tdClass}>{c.name ?? '—'}</td>
                  <td className={tdClass}>{formatDate(c.first_purchase_at)}</td>
                  <td className={tdClass}>{formatMoney(c.total_spent_cents)}</td>
                  <td className={tdClass}>{c.purchase_count}</td>
                </tr>
              ))}
            </tbody>
          </TableShell>
          <Pagination page={page} perPage={perPage} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
