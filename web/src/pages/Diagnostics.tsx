import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { Button, ErrorBanner, LoadingBlock, PageHeader } from '../components/ui';

interface CheckResult {
  status: string;
  detail: string;
  errored_accounts?: { account_id: string; label: string; last_error: string | null }[];
  recent?: { account_id: string; status: string; items_synced: number; created_at: string | null }[];
}

interface DiagnosticsData {
  overall: string;
  checks: Record<string, CheckResult>;
}

const CHECK_LABELS: Record<string, string> = {
  database: 'Database',
  migrations: 'Migrations',
  env_config: 'Environment config',
  gumroad_auth: 'Gumroad authorization',
  sync: 'Sync engine',
  scheduler: 'Scheduler',
  error_log: 'Error log (24h)',
};

export default function Diagnostics() {
  const [data, setData] = useState<DiagnosticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .diagnostics()
      .then((d) => setData(d as DiagnosticsData))
      .catch((e: unknown) => setError(e))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="Diagnostics"
        description="Live system health checks. Nothing here exposes secrets."
        actions={
          <Button variant="secondary" onClick={load} disabled={loading}>
            Re-run checks
          </Button>
        }
      />
      {loading && !data && <LoadingBlock label="Running checks…" />}
      {error ? <ErrorBanner error={error} onRetry={load} /> : null}
      {data && (
        <>
          <div
            className={`mb-4 rounded px-4 py-3 font-semibold ${
              data.overall === 'PASS'
                ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
            }`}
          >
            Overall: {data.overall}
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {Object.entries(data.checks).map(([key, c]) => (
              <div key={key} className="rounded border border-gray-200 p-4 dark:border-gray-800">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-gray-900 dark:text-white">
                    {CHECK_LABELS[key] ?? key}
                  </h3>
                  <span
                    className={`rounded px-2 py-0.5 text-sm font-semibold ${
                      c.status === 'PASS'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300'
                        : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300'
                    }`}
                  >
                    {c.status}
                  </span>
                </div>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{c.detail}</p>
                {c.errored_accounts && c.errored_accounts.length > 0 && (
                  <ul className="mt-2 list-disc pl-5 text-sm text-red-600 dark:text-red-400">
                    {c.errored_accounts.map((a) => (
                      <li key={a.account_id}>
                        {a.label}: {a.last_error}
                      </li>
                    ))}
                  </ul>
                )}
                {c.recent && c.recent.length > 0 && (
                  <ul className="mt-2 space-y-1 text-sm text-gray-600 dark:text-gray-400">
                    {c.recent.map((s, i) => (
                      <li key={i}>
                        {s.status} — {s.items_synced} items
                        {s.created_at ? ` (${s.created_at})` : ''}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
