import { useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../api/client';
import type { ActionResult, Sale } from '../api/types';
import { accountQuery, useApp } from '../context/AppContext';
import { usePaginated } from '../hooks/usePaginated';
import { formatDateTime, formatMoney } from '../utils';
import {
  Badge,
  Button,
  Checkbox,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  LoadingBlock,
  PageHeader,
  Pagination,
  TableShell,
  tdClass,
  thClass,
} from '../components/ui';

type SaleAction = 'refund' | 'mark-shipped';

function SaleActionDialog({
  sale,
  action,
  onClose,
  onDone,
}: {
  sale: Sale;
  action: SaleAction;
  onClose: () => void;
  onDone: () => void;
}) {
  const [dryRun, setDryRun] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<ActionResult | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r =
        action === 'refund'
          ? await api.refundSale(sale.gumroad_id, dryRun)
          : await api.markShipped(sale.gumroad_id, dryRun);
      setResult(r);
      if (!dryRun && r.success) onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const title = action === 'refund' ? 'Refund sale' : 'Mark sale as shipped';
  return (
    <ConfirmDialog
      open
      title={title}
      confirmLabel={dryRun ? 'Run dry-run' : action === 'refund' ? 'Refund for real' : 'Mark shipped for real'}
      danger={!dryRun}
      loading={busy}
      onCancel={onClose}
      onConfirm={() => {
        // submit via form for a11y; this button mirrors the form submit
        const form = document.getElementById('sale-action-form');
        if (form instanceof HTMLFormElement) form.requestSubmit();
      }}
      message={
        <form id="sale-action-form" onSubmit={submit} className="space-y-3">
          <p>
            Sale <span className="font-medium">{formatMoney(sale.amount_cents, sale.currency)}</span>
            {sale.product_name ? ` — ${sale.product_name}` : ''} ({sale.email ?? 'unknown buyer'}).
          </p>
          <Field label="Dry run" htmlFor="dry-run" hint="Dry run only simulates the action. Uncheck to execute it for real on Gumroad.">
            <div className="flex items-center gap-2">
              <Checkbox id="dry-run" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              <span className="text-sm">Dry run (recommended first)</span>
            </div>
          </Field>
          {!dryRun && (
            <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300" role="alert">
              This will perform a REAL {action === 'refund' ? 'refund' : 'mark-as-shipped'} on Gumroad. This cannot be undone.
            </p>
          )}
          {error ? <ErrorBanner error={error} /> : null}
          {result && (
            <p className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-blue-800 dark:border-blue-900/50 dark:bg-blue-950/40 dark:text-blue-300" role="status">
              {result.dry_run ? '[Dry run] ' : ''}{result.message}
            </p>
          )}
        </form>
      }
    />
  );
}

export default function Sales() {
  const { selectedAccountId } = useApp();
  const q0 = accountQuery(selectedAccountId).account_id;
  const { page, setPage, q, setQ, data, loading, error, reload, perPage } = usePaginated(api.sales, q0);
  const [dialog, setDialog] = useState<{ sale: Sale; action: SaleAction } | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<unknown>(null);

  const exportCsv = async () => {
    setExporting(true);
    setExportError(null);
    try {
      await api.exportSalesCsv(q0);
    } catch (e) {
      setExportError(e);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Sales"
        description="Every synced sale. Refunds and mark-as-shipped run dry by default."
        actions={
          <Button variant="secondary" onClick={exportCsv} disabled={exporting}>
            {exporting ? 'Exporting…' : 'Export CSV'}
          </Button>
        }
      />
      {exportError ? <div className="mb-4"><ErrorBanner error={exportError} /></div> : null}
      <div className="mb-4 max-w-sm">
        <label htmlFor="sale-search" className="sr-only">Search sales</label>
        <Input id="sale-search" placeholder="Search by product or buyer email…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>

      {loading && !data && <LoadingBlock />}
      {error ? <ErrorBanner error={error} onRetry={reload} /> : null}

      {data && data.items.length === 0 && !loading && (
        <EmptyState title="No sales found" description={q ? 'Try a different search.' : 'Sync a Gumroad account to pull in sales.'} />
      )}

      {data && data.items.length > 0 && (
        <>
          <TableShell>
            <thead className="bg-gray-50 dark:bg-gray-800/60">
              <tr>
                <th className={thClass}>Date</th>
                <th className={thClass}>Product</th>
                <th className={thClass}>Buyer</th>
                <th className={thClass}>Amount</th>
                <th className={thClass}>Status</th>
                <th className={thClass}>Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
              {data.items.map((s) => (
                <tr key={s.id}>
                  <td className={tdClass}>{formatDateTime(s.created_at)}</td>
                  <td className={tdClass}>{s.product_name ?? '—'}</td>
                  <td className={tdClass}>{s.email ?? '—'}</td>
                  <td className={tdClass}>{formatMoney(s.amount_cents, s.currency)}</td>
                  <td className={tdClass}>
                    <div className="flex gap-1">
                      {s.refunded && <Badge tone="red">Refunded</Badge>}
                      {!s.refunded && <Badge tone="green">Paid</Badge>}
                      {s.shipped && <Badge tone="blue">Shipped</Badge>}
                      {s.is_subscription && <Badge tone="purple">Subscription</Badge>}
                    </div>
                  </td>
                  <td className={tdClass}>
                    <div className="flex gap-2">
                      {!s.refunded && (
                        <Button variant="secondary" onClick={() => setDialog({ sale: s, action: 'refund' })}>
                          Refund
                        </Button>
                      )}
                      {!s.shipped && (
                        <Button variant="secondary" onClick={() => setDialog({ sale: s, action: 'mark-shipped' })}>
                          Mark shipped
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableShell>
          <Pagination page={page} perPage={perPage} total={data.total} onPage={setPage} />
        </>
      )}

      {dialog && (
        <SaleActionDialog
          sale={dialog.sale}
          action={dialog.action}
          onClose={() => setDialog(null)}
          onDone={() => {
            setDialog(null);
            reload();
          }}
        />
      )}
    </div>
  );
}
