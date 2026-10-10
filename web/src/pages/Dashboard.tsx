import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AnalyticsData, DashboardData } from '../api/types';
import { accountQuery, useApp } from '../context/AppContext';
import { formatDateTime, formatMoney } from '../utils';
import { Button, EmptyState, ErrorBanner, LoadingBlock, PageHeader, StatCard, TableShell, tdClass, thClass } from '../components/ui';

const PRESETS = [
  { key: 'all', label: 'All time' },
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'Last 7 days' },
  { key: 'month', label: 'Last 30 days' },
  { key: 'year', label: 'Last year' },
];

export default function Dashboard() {
  const { selectedAccountId } = useApp();
  const [data, setData] = useState<DashboardData | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [preset, setPreset] = useState('all');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const q = accountQuery(selectedAccountId);
    const aParams: { account_id?: string; preset?: string; start_date?: string; end_date?: string } = {};
    if (q.account_id) aParams.account_id = q.account_id;
    if (startDate && endDate) {
      aParams.start_date = startDate;
      aParams.end_date = endDate;
    } else {
      aParams.preset = preset;
    }
    Promise.all([api.dashboard(q.account_id), api.analytics(aParams)])
      .then(([d, a]) => {
        setData(d);
        setAnalytics(a);
      })
      .catch((e: unknown) => setError(e))
      .finally(() => setLoading(false));
  }, [selectedAccountId, preset, startDate, endDate]);

  useEffect(() => {
    load();
  }, [load]);

  const maxTrend = analytics ? Math.max(1, ...analytics.daily_trend.map((d) => d.gross_cents)) : 1;

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

      {/* Date range filter */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {PRESETS.map((p) => (
          <Button
            key={p.key}
            variant={preset === p.key && !startDate ? 'primary' : 'secondary'}
            onClick={() => {
              setPreset(p.key);
              setStartDate('');
              setEndDate('');
            }}
          >
            {p.label}
          </Button>
        ))}
        <input
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        />
        <span className="text-sm text-gray-500">to</span>
        <input
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          className="rounded border border-gray-300 px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-800"
        />
      </div>

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

          {analytics && (
            <>
              <h2 className="mb-3 mt-8 text-lg font-semibold text-gray-900 dark:text-white">
                Sales analytics{analytics.range.start ? ` (${analytics.range.start} → ${analytics.range.end})` : ''}
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <StatCard label="Gross sales" value={formatMoney(analytics.gross_cents)} />
                <StatCard label="Refunded" value={formatMoney(analytics.refunded_cents)} />
                <StatCard label="Net revenue" value={formatMoney(analytics.net_cents)} />
                <StatCard
                  label="Refunds / Disputed"
                  value={`${analytics.refunded_count} / ${analytics.disputed_count}`}
                />
              </div>

              <h3 className="mb-3 mt-8 text-md font-semibold text-gray-900 dark:text-white">Daily trend</h3>
              {analytics.daily_trend.length === 0 || analytics.daily_trend.every((d) => d.gross_cents === 0) ? (
                <EmptyState title="No sales in this period" description="Try a wider date range." />
              ) : (
                <div className="flex h-32 items-end gap-1 overflow-x-auto rounded border border-gray-200 p-3 dark:border-gray-800">
                  {analytics.daily_trend.map((d) => (
                    <div
                      key={d.date}
                      title={`${d.date}: ${formatMoney(d.gross_cents)} (${d.sales_count} sales)`}
                      className="min-w-2 flex-1 rounded-t bg-blue-500 hover:bg-blue-600"
                      style={{ height: `${Math.max(2, (d.gross_cents / maxTrend) * 100)}%` }}
                    />
                  ))}
                </div>
              )}

              <h3 className="mb-3 mt-8 text-md font-semibold text-gray-900 dark:text-white">Revenue by product</h3>
              {analytics.per_product.length === 0 ? (
                <EmptyState title="No products" description="Sync an account to pull in products." />
              ) : (
                <TableShell>
                  <thead className="bg-gray-50 dark:bg-gray-800/60">
                    <tr>
                      <th className={thClass}>Product</th>
                      <th className={thClass}>Price</th>
                      <th className={thClass}>Sales</th>
                      <th className={thClass}>Gross revenue</th>
                      <th className={thClass}>Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                    {analytics.per_product.map((p) => (
                      <tr key={p.product_id}>
                        <td className={tdClass}>{p.name}</td>
                        <td className={tdClass}>{formatMoney(p.price_cents)}</td>
                        <td className={tdClass}>{p.sales_count}</td>
                        <td className={tdClass}>{formatMoney(p.gross_cents)}</td>
                        <td className={tdClass}>{p.published ? 'Published' : 'Draft'}</td>
                      </tr>
                    ))}
                  </tbody>
                </TableShell>
              )}

              {analytics.no_sale_products.length > 0 && (
                <>
                  <h3 className="mb-3 mt-8 text-md font-semibold text-gray-900 dark:text-white">
                    Products with no sales ({analytics.no_sale_products.length})
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {analytics.no_sale_products.map((p) => (
                      <span
                        key={p.product_id}
                        className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                      >
                        {p.name}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

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
