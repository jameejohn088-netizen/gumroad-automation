import { api } from '../api/client';
import { accountQuery, useApp } from '../context/AppContext';
import { usePaginated } from '../hooks/usePaginated';
import { Badge, EmptyState, ErrorBanner, Input, LoadingBlock, PageHeader, Pagination, TableShell, tdClass, thClass } from '../components/ui';

export default function Memberships() {
  const { selectedAccountId } = useApp();
  const q0 = accountQuery(selectedAccountId).account_id;
  const { page, setPage, q, setQ, data, loading, error, reload, perPage } = usePaginated(api.memberships, q0);

  return (
    <div>
      <PageHeader title="Memberships" description="Derived from subscription products and their subscribers." />
      <div className="mb-4 max-w-sm">
        <label htmlFor="membership-search" className="sr-only">Search memberships</label>
        <Input id="membership-search" placeholder="Search memberships…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && !data && <LoadingBlock />}
      {error ? <ErrorBanner error={error} onRetry={reload} /> : null}

      {data && data.items.length === 0 && !loading && (
        <EmptyState title="No memberships found" description={q ? 'Try a different search.' : 'Memberships appear after syncing subscription products.'} />
      )}

      {data && data.items.length > 0 && (
        <>
          <TableShell>
            <thead className="bg-gray-50 dark:bg-gray-800/60">
              <tr>
                <th className={thClass}>Product</th>
                <th className={thClass}>Tier</th>
                <th className={thClass}>Subscribers</th>
                <th className={thClass}>Billing</th>
                <th className={thClass}>Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              {data.items.map((m) => (
                <tr key={m.id}>
                  <td className={tdClass}>{m.product_name}</td>
                  <td className={tdClass}>{m.tier_name ?? '—'}</td>
                  <td className={tdClass}>{m.subscriber_count}</td>
                  <td className={tdClass}>{m.recurrence ?? '—'}</td>
                  <td className={tdClass}>
                    <Badge tone={m.status === 'active' ? 'green' : 'gray'}>{m.status}</Badge>
                  </td>
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
