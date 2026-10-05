import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AppNotification } from '../api/types';
import { formatDateTime } from '../utils';
import { Badge, Button, Card, EmptyState, ErrorBanner, LoadingBlock, PageHeader } from '../components/ui';

export default function Notifications() {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .notifications()
      .then(setItems)
      .catch((e: unknown) => setError(e))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const markRead = async (id: string) => {
    setBusy(id);
    try {
      await api.markNotificationRead(id);
      setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  const unread = items.filter((n) => !n.read).length;

  return (
    <div>
      <PageHeader
        title="Notifications"
        description={unread > 0 ? `${unread} unread` : 'All caught up.'}
        actions={<Button variant="secondary" onClick={load} disabled={loading}>Refresh</Button>}
      />

      {loading && <LoadingBlock label="Loading notifications…" />}
      {error ? <ErrorBanner error={error} onRetry={load} /> : null}

      {!loading && items.length === 0 && (
        <EmptyState title="No notifications" description="Automation alerts and system events will appear here." />
      )}

      <div className="space-y-3">
        {items.map((n) => (
          <Card key={n.id} className={`p-4 ${n.read ? 'opacity-70' : 'border-l-4 border-l-blue-500'}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold text-gray-900 dark:text-white">{n.title}</h2>
                  {!n.read && <Badge tone="blue">New</Badge>}
                </div>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-300">{n.message}</p>
                <p className="mt-1 text-xs text-gray-400">{formatDateTime(n.created_at)}</p>
              </div>
              {!n.read && (
                <Button variant="secondary" disabled={busy === n.id} onClick={() => markRead(n.id)}>
                  {busy === n.id ? 'Marking…' : 'Mark as read'}
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
