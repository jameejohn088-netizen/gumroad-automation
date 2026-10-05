import { api } from '../api/client';
import { accountQuery, useApp } from '../context/AppContext';
import { usePaginated } from '../hooks/usePaginated';
import { formatDate } from '../utils';
import { Badge, EmptyState, ErrorBanner, Input, LoadingBlock, PageHeader, Pagination, TableShell, tdClass, thClass } from '../components/ui';

export default function Subscribers() {
  const { selectedAccountId } = useApp();
  const q0 = accountQuery(selectedAccountId).account_id;
  const { page, setPage, q, setQ, data, loading, error, reload, perPage } = usePaginated(api.subscribers, q0);

  return (
    <div>
      <PageHeader title="Subscribers" description="Subscription customers synced from Gumroad." />
      <div className="mb-4 max-w-sm">
        <label htmlFor="subscriber-search" className="sr-only">Search subscribers</label>
        <Input id="subscriber-search" placeholder="Search by email or product…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && !data && <LoadingBlock />}
      {error ? <ErrorBanner error={error} onRetry={reload} /> : null}

      {data && data.items.length === 0 && !loading && (
        <EmptyState title="No subscribers found" description={q ? 'Try a different search.' : 'Subscribers appear after syncing an account with subscription products.'} />
      )}

      {data && data.items.length > 0 && (
        <>
          <TableShell>
            <thead className="bg-gray-50 dark:bg-gray-800/60">
              <tr>
                <th className={thClass}>Email</th>
                <th className={thClass}>Product</th>
                <th className={thClass}>Status</th>
                <th className={thClass}>Since</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              {data.items.map((s) => (
                <tr key={s.id}>
                  <td className={tdClass}>{s.email ?? '—'}</td>
                  <td className={tdClass}>{s.product_name ?? '—'}</td>
                  <td className={tdClass}>
                    <Badge tone={s.status === 'alive' ? 'green' : s.status === 'cancelled' ? 'red' : 'gray'}>{s.status}</Badge>
                  </td>
                  <td className={tdClass}>{formatDate(s.created_at)}</td>
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
