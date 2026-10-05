import { useState } from 'react';
import { api } from '../api/client';
import { accountQuery, useApp } from '../context/AppContext';
import { usePaginated } from '../hooks/usePaginated';
import { formatDateTime } from '../utils';
import { EmptyState, ErrorBanner, LoadingBlock, PageHeader, Pagination, TableShell, tdClass, thClass } from '../components/ui';

type Tab = 'activity' | 'errors';

export default function Logs() {
  const { selectedAccountId } = useApp();
  const q0 = accountQuery(selectedAccountId).account_id;
  const [tab, setTab] = useState<Tab>('activity');

  const activity = usePaginated(api.activityLogs, q0);
  const errors = usePaginated(api.errorLogs, q0);

  const tabClass = (t: Tab) =>
    `rounded-lg px-4 py-2 text-sm font-medium ${
      tab === t
        ? 'bg-blue-600 text-white'
        : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
    }`;

  const renderActivity = () => {
    if (activity.loading && !activity.data) return <LoadingBlock />;
    return (
      <>
        {activity.error ? <ErrorBanner error={activity.error} onRetry={activity.reload} /> : null}
        {activity.data && activity.data.items.length === 0 && !activity.loading && (
          <EmptyState title="No activity yet" description="A clean slate." />
        )}
        {activity.data && activity.data.items.length > 0 && (
          <>
            <TableShell>
              <thead className="bg-gray-50 dark:bg-gray-800/60">
                <tr>
                  <th className={thClass}>Time</th>
                  <th className={thClass}>Action</th>
                  <th className={thClass}>Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                {activity.data.items.map((l) => (
                  <tr key={l.id}>
                    <td className={`${tdClass} whitespace-nowrap`}>{formatDateTime(l.created_at)}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{l.action}</td>
                    <td className={tdClass}>{l.message}</td>
                  </tr>
                ))}
              </tbody>
            </TableShell>
            <Pagination page={activity.page} perPage={activity.perPage} total={activity.data.total} onPage={activity.setPage} />
          </>
        )}
      </>
    );
  };

  const renderErrors = () => {
    if (errors.loading && !errors.data) return <LoadingBlock />;
    return (
      <>
        {errors.error ? <ErrorBanner error={errors.error} onRetry={errors.reload} /> : null}
        {errors.data && errors.data.items.length === 0 && !errors.loading && (
          <EmptyState title="No errors recorded" description="A clean slate." />
        )}
        {errors.data && errors.data.items.length > 0 && (
          <>
            <TableShell>
              <thead className="bg-gray-50 dark:bg-gray-800/60">
                <tr>
                  <th className={thClass}>Time</th>
                  <th className={thClass}>Message</th>
                  <th className={thClass}>Correlation ID</th>
                  <th className={thClass}>Context</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                {errors.data.items.map((l) => (
                  <tr key={l.id}>
                    <td className={`${tdClass} whitespace-nowrap`}>{formatDateTime(l.created_at)}</td>
                    <td className={tdClass}>{l.message}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{l.correlation_id ?? '—'}</td>
                    <td className={`${tdClass} font-mono text-xs`}>{l.context ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </TableShell>
            <Pagination page={errors.page} perPage={errors.perPage} total={errors.data.total} onPage={errors.setPage} />
          </>
        )}
      </>
    );
  };

  return (
    <div>
      <PageHeader title="Logs" description="Activity trail and error records. Tokens are redacted; emails masked." />

      <div className="mb-4 flex gap-2" role="tablist" aria-label="Log type">
        <button role="tab" aria-selected={tab === 'activity'} className={tabClass('activity')} onClick={() => setTab('activity')}>
          Activity
        </button>
        <button role="tab" aria-selected={tab === 'errors'} className={tabClass('errors')} onClick={() => setTab('errors')}>
          Errors
        </button>
      </div>

      {tab === 'activity' ? renderActivity() : renderErrors()}
    </div>
  );
}
