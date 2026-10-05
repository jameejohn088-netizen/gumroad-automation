import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { DashboardData } from '../api/types';
import { accountQuery, useApp } from '../context/AppContext';
import { formatDateTime, formatMoney } from '../utils';
import { Button, EmptyState, ErrorBanner, LoadingBlock, PageHeader, StatCard, TableShell, tdClass, thClass } from '../components/ui';

export default function Dashboard() {
  const { selectedAccountId } = useApp();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .dashboard(accountQuery(selectedAccountId).account_id)
      .then((d) => setData(d))
      .catch((e: unknown) => setError(e))
      .finally(() => setLoading(false));
  }, [selectedAccountId]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Live aggregates from your synced Gumroad data."
        actions={
          <Button variant="secondary" onClick={load} disabled={loading}>
            Refresh
          </Button>
        }
      />

      {loading && !data && <LoadingBlock label="Loading dashboard…" />}
      {error ? <ErrorBanner error={error} onRetry={load} /> : null}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <StatCard label="Revenue" value={formatMoney(data.revenue_cents)} />
            <StatCard label="Sales" value={String(data.sales_count)} />
            <StatCard label="Customers" value={String(data.customers_count)} />
            <StatCard label="Subscribers" value={String(data.subscribers_count)} />
            <StatCard label="Products" value={String(data.products_count)} />
          </div>

          <h2 className="mb-3 mt-8 text-lg font-semibold text-gray-900 dark:text-white">Recent sales</h2>
          {data.recent_sales.length === 0 ? (
            <EmptyState
              title="No sales yet"
              description="Sync a Gumroad account to pull in sales. Use the Accounts page to connect and sync."
            />
          ) : (
            <TableShell>
              <thead className="bg-gray-50 dark:bg-gray-800/60">
                <tr>
                  <th className={thClass}>Date</th>
                  <th className={thClass}>Product</th>
                  <th className={thClass}>Buyer</th>
                  <th className={thClass}>Amount</th>
                  <th className={thClass}>Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                {data.recent_sales.map((s) => (
                  <tr key={s.id}>
                    <td className={tdClass}>{formatDateTime(s.created_at)}</td>
                    <td className={tdClass}>{s.product_name ?? '—'}</td>
                    <td className={tdClass}>{s.email ?? '—'}</td>
                    <td className={tdClass}>{formatMoney(s.amount_cents, s.currency)}</td>
                    <td className={tdClass}>{s.refunded ? 'Refunded' : 'Paid'}</td>
                  </tr>
                ))}
              </tbody>
            </TableShell>
          )}
        </>
      )}
    </div>
  );
}
