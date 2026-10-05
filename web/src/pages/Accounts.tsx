import { useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../api/client';
import type { AccountStatus, GumroadAccount, SyncHistoryItem } from '../api/types';
import { useApp } from '../context/AppContext';
import { timeAgo } from '../utils';
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  LoadingBlock,
  PageHeader,
} from '../components/ui';

const statusTone: Record<AccountStatus, 'green' | 'yellow' | 'red' | 'gray'> = {
  connected: 'green',
  needs_reconnect: 'yellow',
  error: 'red',
  disabled: 'gray',
};

const statusLabel: Record<AccountStatus, string> = {
  connected: 'Connected',
  needs_reconnect: 'Needs reconnect',
  error: 'Error',
  disabled: 'Disabled',
};

export default function Accounts() {
  const { accounts, accountsLoading, refreshAccounts } = useApp();
  const [pageError, setPageError] = useState<unknown>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [newName, setNewName] = useState('');
  const [adding, setAdding] = useState(false);

  const [tokenFor, setTokenFor] = useState<string | null>(null);
  const [token, setToken] = useState('');
  const [historyFor, setHistoryFor] = useState<string | null>(null);
  const [history, setHistory] = useState<SyncHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState<GumroadAccount | null>(null);

  const run = async (key: string, fn: () => Promise<unknown>, okMsg?: string) => {
    setActionBusy(key);
    setPageError(null);
    setNotice(null);
    try {
      await fn();
      await refreshAccounts();
      if (okMsg) setNotice(okMsg);
    } catch (e) {
      setPageError(e);
    } finally {
      setActionBusy(null);
    }
  };

  const addAccount = async (e: FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setAdding(true);
    setPageError(null);
    try {
      const acc = await api.createAccount(newName.trim());
      setNewName('');
      await refreshAccounts();
      setTokenFor(acc.id);
      setNotice(`Account "${acc.name}" created. Paste your Gumroad access token below to connect it.`);
    } catch (err) {
      setPageError(err);
    } finally {
      setAdding(false);
    }
  };

  const connectManual = async (e: FormEvent, accountId: string) => {
    e.preventDefault();
    if (!token.trim()) return;
    await run(`connect-${accountId}`, () => api.connectManual(accountId, token.trim()), 'Account connected and validated.');
    setToken('');
    setTokenFor(null);
  };

  const toggleHistory = async (accountId: string) => {
    if (historyFor === accountId) {
      setHistoryFor(null);
      return;
    }
    setHistoryFor(accountId);
    setHistoryLoading(true);
    try {
      setHistory(await api.syncHistory(accountId));
    } catch (e) {
      setPageError(e);
      setHistoryFor(null);
    } finally {
      setHistoryLoading(false);
    }
  };

  return (
    <div>
      <PageHeader title="Gumroad Accounts" description="Connect as many Gumroad accounts as you need — each stays fully isolated." />

      {pageError ? <div className="mb-4"><ErrorBanner error={pageError} /></div> : null}
      {notice && (
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-800 dark:border-green-900/50 dark:bg-green-950/40 dark:text-green-300" role="status">
          {notice}
        </div>
      )}

      <Card className="mb-6 p-5">
        <h2 className="text-base font-semibold text-gray-900 dark:text-white">Add Gumroad account</h2>
        <form onSubmit={addAccount} className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <Field label="Account name" htmlFor="new-account-name" required hint="A label for you — e.g. “My store”.">
              <Input
                id="new-account-name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="My Gumroad store"
                required
              />
            </Field>
          </div>
          <Button type="submit" loading={adding}>
            Add account
          </Button>
        </form>
      </Card>

      {accountsLoading && <LoadingBlock label="Loading accounts…" />}

      {!accountsLoading && accounts.length === 0 && (
        <EmptyState
          title="No Gumroad accounts yet"
          description="Add your first account above, then paste a Gumroad access token (generated on your Gumroad OAuth application page) to connect it. Tokens are encrypted on the server and never sent to the browser."
        />
      )}

      <div className="space-y-4">
        {accounts.map((acc) => (
          <Card key={acc.id} className="p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{acc.name}</h2>
                  <Badge tone={statusTone[acc.status]}>{statusLabel[acc.status]}</Badge>
                </div>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Last sync: {timeAgo(acc.last_sync_at)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  disabled={actionBusy !== null}
                  onClick={() =>
                    run(`sync-${acc.id}`, async () => {
                      const r = await api.syncAccount(acc.id);
                      return r;
                    }, 'Sync started — check Scheduler for progress.')
                  }
                >
                  {actionBusy === `sync-${acc.id}` ? 'Starting…' : 'Sync now'}
                </Button>
                {acc.status === 'disabled' ? (
                  <Button variant="secondary" disabled={actionBusy !== null} onClick={() => run(`enable-${acc.id}`, () => api.enableAccount(acc.id), 'Account enabled.')}>
                    Enable
                  </Button>
                ) : (
                  <Button variant="secondary" disabled={actionBusy !== null} onClick={() => run(`disable-${acc.id}`, () => api.disableAccount(acc.id), 'Account disabled.')}>
                    Disable
                  </Button>
                )}
                <Button variant="secondary" disabled={actionBusy !== null} onClick={() => run(`reconnect-${acc.id}`, () => api.reconnectAccount(acc.id), 'Reconnect attempted with the stored token.')}>
                  Reconnect
                </Button>
                <Button variant="secondary" disabled={actionBusy !== null} onClick={() => run(`disconnect-${acc.id}`, () => api.disconnectAccount(acc.id), 'Account disconnected. Stored data is kept.')}>
                  Disconnect
                </Button>
                <Button variant="secondary" disabled={actionBusy !== null} onClick={() => toggleHistory(acc.id)}>
                  {historyFor === acc.id ? 'Hide sync history' : 'Sync history'}
                </Button>
                <Button variant="danger" disabled={actionBusy !== null} onClick={() => setDeleteTarget(acc)}>
                  Remove
                </Button>
              </div>
            </div>

            {(acc.status === 'needs_reconnect' || acc.status === 'error' || tokenFor === acc.id) && (
              <form onSubmit={(e) => connectManual(e, acc.id)} className="mt-4 rounded-lg bg-gray-50 p-4 dark:bg-gray-800/60">
                <Field
                  label="Gumroad access token"
                  htmlFor={`token-${acc.id}`}
                  required
                  hint="Generate it on your Gumroad OAuth application page (“Generate access token”). Paste it here — it goes straight to the backend over HTTPS and is stored encrypted. Never share it in chat."
                >
                  <Input
                    id={`token-${acc.id}`}
                    type="password"
                    autoComplete="off"
                    value={tokenFor === acc.id ? token : ''}
                    onChange={(e) => {
                      setTokenFor(acc.id);
                      setToken(e.target.value);
                    }}
                    placeholder="Paste access token"
                    required
                  />
                </Field>
                <div className="mt-3 flex gap-2">
                  <Button type="submit" loading={actionBusy === `connect-${acc.id}`}>
                    Connect
                  </Button>
                  {tokenFor === acc.id && (
                    <Button variant="secondary" type="button" onClick={() => { setTokenFor(null); setToken(''); }}>
                      Cancel
                    </Button>
                  )}
                </div>
              </form>
            )}

            {historyFor === acc.id && (
              <div className="mt-4">
                {historyLoading ? (
                  <LoadingBlock label="Loading sync history…" />
                ) : history.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">No sync runs recorded yet.</p>
                ) : (
                  <ul className="divide-y divide-gray-200 text-sm dark:divide-gray-800">
                    {history.map((h) => (
                      <li key={h.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                        <span className="text-gray-700 dark:text-gray-300">
                          {new Date(h.started_at).toLocaleString()} → {h.finished_at ? new Date(h.finished_at).toLocaleString() : 'running'}
                        </span>
                        <span className="flex items-center gap-2">
                          <Badge tone={h.status === 'success' ? 'green' : h.status === 'failed' ? 'red' : 'yellow'}>{h.status}</Badge>
                          {h.error && <span className="text-xs text-red-600 dark:text-red-400">{h.error}</span>}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </Card>
        ))}
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Remove Gumroad account?"
        message={
          <p>
            This will permanently delete <span className="font-medium">“{deleteTarget?.name}”</span> and all of its
            synced data — products, sales, customers, subscribers, automations, jobs and logs. This cannot be undone.
          </p>
        }
        confirmLabel="Remove permanently"
        danger
        loading={actionBusy === `delete-${deleteTarget?.id}`}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (!deleteTarget) return;
          const id = deleteTarget.id;
          setDeleteTarget(null);
          void run(`delete-${id}`, () => api.deleteAccount(id), 'Account removed.');
        }}
      />
    </div>
  );
}
