import { api } from '../api/client';
import { accountQuery, useApp } from '../context/AppContext';
import { usePaginated } from '../hooks/usePaginated';
import { formatDate, formatMoney } from '../utils';
import { Badge, EmptyState, ErrorBanner, Input, LoadingBlock, PageHeader, Pagination, TableShell, tdClass, thClass } from '../components/ui';

export default function Products() {
  const { selectedAccountId } = useApp();
  const q0 = accountQuery(selectedAccountId).account_id;
  const { page, setPage, q, setQ, data, loading, error, reload, perPage } = usePaginated(api.products, q0);

  return (
    <div>
      <PageHeader title="Products" description="Products synced from your Gumroad accounts." />
      <div className="mb-4 max-w-sm">
        <label htmlFor="product-search" className="sr-only">Search products</label>
        <Input id="product-search" placeholder="Search products…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && !data && <LoadingBlock />}
      {error ? <ErrorBanner error={error} onRetry={reload} /> : null}

      {data && data.items.length === 0 && !loading && (
        <EmptyState
          title="No products found"
          description={q ? 'Try a different search.' : 'Sync a Gumroad account to pull in products.'}
        />
      )}

      {data && data.items.length > 0 && (
        <>
          <TableShell>
            <thead className="bg-gray-50 dark:bg-gray-800/60">
              <tr>
                <th className={thClass}>Product</th>
                <th className={thClass}>Price</th>
                <th className={thClass}>Published</th>
                <th className={thClass}>Sales</th>
                <th className={thClass}>Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              {data.items.map((p) => (
                <tr key={p.id}>
                  <td className={tdClass}>
                    <div className="flex items-center gap-3">
                      {p.thumbnail_url && (
                        <img src={p.thumbnail_url} alt="" className="h-10 w-10 rounded object-cover" loading="lazy" />
                      )}
                      <span className="font-medium">{p.name}</span>
                    </div>
                  </td>
                  <td className={tdClass}>{formatMoney(p.price_cents, p.currency)}</td>
                  <td className={tdClass}>
                    <Badge tone={p.published ? 'green' : 'gray'}>{p.published ? 'Published' : 'Draft'}</Badge>
                  </td>
                  <td className={tdClass}>{p.sales_count}</td>
                  <td className={tdClass}>{formatDate(p.updated_at)}</td>
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
