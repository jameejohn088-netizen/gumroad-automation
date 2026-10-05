import { api } from '../api/client';
import { accountQuery, useApp } from '../context/AppContext';
import { usePaginated } from '../hooks/usePaginated';
import { formatDate } from '../utils';
import { Badge, EmptyState, ErrorBanner, Input, LoadingBlock, PageHeader, Pagination, TableShell, tdClass, thClass } from '../components/ui';

function maskKey(key: string | null): string {
  if (!key) return '—';
  if (key.length <= 8) return '••••';
  return `${key.slice(0, 4)}••••${key.slice(-4)}`;
}

export default function Licenses() {
  const { selectedAccountId } = useApp();
  const q0 = accountQuery(selectedAccountId).account_id;
  const { page, setPage, q, setQ, data, loading, error, reload, perPage } = usePaginated(api.licenses, q0);

  return (
    <div>
      <PageHeader title="Licenses" description="License keys for your products. Keys are partially masked." />
      <div className="mb-4 max-w-sm">
        <label htmlFor="license-search" className="sr-only">Search licenses</label>
        <Input id="license-search" placeholder="Search by product or email…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && !data && <LoadingBlock />}
      {error ? <ErrorBanner error={error} onRetry={reload} /> : null}

      {data && data.items.length === 0 && !loading && (
        <EmptyState title="No licenses found" description={q ? 'Try a different search.' : 'Licenses appear after syncing products that issue license keys.'} />
      )}

      {data && data.items.length > 0 && (
        <>
          <TableShell>
            <thead className="bg-gray-50 dark:bg-gray-800/60">
              <tr>
                <th className={thClass}>Key</th>
                <th className={thClass}>Product</th>
                <th className={thClass}>Email</th>
                <th className={thClass}>Uses</th>
                <th className={thClass}>Status</th>
                <th className={thClass}>Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              {data.items.map((l) => (
                <tr key={l.id}>
                  <td className={`${tdClass} font-mono text-xs`}>{maskKey(l.key)}</td>
                  <td className={tdClass}>{l.product_name ?? '—'}</td>
                  <td className={tdClass}>{l.email ?? '—'}</td>
                  <td className={tdClass}>{l.uses ?? '—'}</td>
                  <td className={tdClass}>
                    <Badge tone={l.enabled ? 'green' : 'gray'}>{l.enabled ? 'Enabled' : 'Disabled'}</Badge>
                  </td>
                  <td className={tdClass}>{formatDate(l.created_at)}</td>
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
