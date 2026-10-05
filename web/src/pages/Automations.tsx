import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../api/client';
import type { AutomationRule, AutomationRuleInput, RuleAction, RuleCondition, RuleTrigger } from '../api/types';
import { ALL_ACCOUNTS, accountQuery, useApp } from '../context/AppContext';
import { formatDateTime } from '../utils';
import {
  Badge,
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  LoadingBlock,
  PageHeader,
  Select,
  Textarea,
} from '../components/ui';

const TRIGGERS: { value: RuleTrigger; label: string }[] = [
  { value: 'new_sale', label: 'New sale' },
  { value: 'refund', label: 'Refund issued' },
  { value: 'new_subscriber', label: 'New subscriber' },
  { value: 'subscription_cancelled', label: 'Subscription cancelled (detected by polling)' },
  { value: 'subscription_ended', label: 'Subscription ended (detected by polling)' },
  { value: 'product_change', label: 'Product changed' },
  { value: 'schedule', label: 'On a schedule' },
  { value: 'sales_threshold', label: 'Sales threshold reached' },
];

const CONDITION_FIELDS = [
  'product',
  'amount',
  'currency',
  'buyer_email_domain',
  'is_subscription',
  'account',
  'time_window',
  'first_time_buyer',
];

const OPERATORS = ['equals', 'not_equals', 'contains', 'greater_than', 'less_than', 'greater_or_equal', 'less_or_equal'];

const ACTIONS: { value: string; label: string; configHint: string }[] = [
  { value: 'notification', label: 'In-app notification', configHint: '{"title": "...", "message": "..."}' },
  { value: 'offer_code_create', label: 'Create offer code', configHint: '{"code": "SAVE10", "amount_cents": 1000}' },
  { value: 'offer_code_update', label: 'Update offer code', configHint: '{"code": "SAVE10", "amount_cents": 2000}' },
  { value: 'offer_code_delete', label: 'Delete offer code', configHint: '{"code": "SAVE10"}' },
  { value: 'license_enable', label: 'Enable license', configHint: '{"license_key": "..."}' },
  { value: 'license_disable', label: 'Disable license', configHint: '{"license_key": "..."}' },
  { value: 'refund', label: 'Refund sale (needs confirmation)', configHint: '{} — always dry-run first' },
  { value: 'mark_shipped', label: 'Mark sale as shipped (needs confirmation)', configHint: '{} — always dry-run first' },
  { value: 'csv_export', label: 'CSV export', configHint: '{"entity": "sales"}' },
  { value: 'daily_summary', label: 'Daily summary', configHint: '{}' },
  { value: 'webhook', label: 'Outbound webhook (your URL)', configHint: '{"url": "https://…"}' },
  { value: 'email', label: 'Email via your SMTP', configHint: '{"to": "you@example.com", "subject": "…"}' },
];

interface BuilderState {
  name: string;
  accountId: string;
  trigger: RuleTrigger;
  conditions: RuleCondition[];
  actions: { type: string; configText: string }[];
  enabled: boolean;
  dryRun: boolean;
}

const emptyBuilder = (): BuilderState => ({
  name: '',
  accountId: ALL_ACCOUNTS,
  trigger: 'new_sale',
  conditions: [],
  actions: [],
  enabled: true,
  dryRun: true,
});

function RuleBuilder({
  initial,
  editingId,
  onSaved,
  onCancel,
}: {
  initial: BuilderState;
  editingId: string | null;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const { accounts } = useApp();
  const [s, setS] = useState<BuilderState>(initial);
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  const set = (patch: Partial<BuilderState>) => setS((prev) => ({ ...prev, ...patch }));

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!s.name.trim()) {
      setError(new Error('Rule name is required.'));
      return;
    }
    if (s.actions.length === 0) {
      setError(new Error('Add at least one action.'));
      return;
    }
    let actions: RuleAction[];
    try {
      actions = s.actions.map((a) => ({
        type: a.type,
        config: a.configText.trim() ? (JSON.parse(a.configText) as Record<string, string>) : undefined,
      }));
    } catch {
      setError(new Error('One of the action configs is not valid JSON.'));
      return;
    }
    const input: AutomationRuleInput = {
      name: s.name.trim(),
      account_id: s.accountId === ALL_ACCOUNTS ? null : s.accountId,
      trigger: s.trigger,
      conditions: s.conditions,
      actions,
      enabled: s.enabled,
      dry_run: s.dryRun,
    };
    setSaving(true);
    try {
      if (editingId) await api.updateRule(editingId, input);
      else await api.createRule(input);
      onSaved();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="mb-6 p-5">
      <h2 className="text-base font-semibold text-gray-900 dark:text-white">
        {editingId ? 'Edit automation rule' : 'New automation rule'}
      </h2>
      <form onSubmit={save} className="mt-4 space-y-5">
        {error ? <ErrorBanner error={error} /> : null}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Rule name" htmlFor="rule-name" required>
            <Input id="rule-name" value={s.name} onChange={(e) => set({ name: e.target.value })} placeholder="e.g. Notify me on big sales" required />
          </Field>
          <Field label="Account" htmlFor="rule-account" hint="Blank scope = all your accounts.">
            <Select id="rule-account" value={s.accountId} onChange={(e) => set({ accountId: e.target.value })}>
              <option value={ALL_ACCOUNTS}>All accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
          </Field>
        </div>

        <Field label="Trigger" htmlFor="rule-trigger" required hint="Only triggers the backend can really detect are listed.">
          <Select id="rule-trigger" value={s.trigger} onChange={(e) => set({ trigger: e.target.value as RuleTrigger })}>
            {TRIGGERS.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </Select>
        </Field>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Conditions <span className="font-normal text-gray-400">(all must match)</span></span>
            <Button type="button" variant="secondary" onClick={() => set({ conditions: [...s.conditions, { field: 'product', operator: 'equals', value: '' }] })}>
              + Add condition
            </Button>
          </div>
          {s.conditions.length === 0 && <p className="text-sm text-gray-400">No conditions — rule fires on every trigger event.</p>}
          <div className="space-y-2">
            {s.conditions.map((c, i) => (
              <div key={i} className="flex flex-col gap-2 sm:flex-row">
                <Select value={c.field} onChange={(e) => { const next = [...s.conditions]; next[i] = { ...c, field: e.target.value }; set({ conditions: next }); }} aria-label="Condition field" className="sm:w-44">
                  {CONDITION_FIELDS.map((f) => <option key={f} value={f}>{f}</option>)}
                </Select>
                <Select value={c.operator} onChange={(e) => { const next = [...s.conditions]; next[i] = { ...c, operator: e.target.value }; set({ conditions: next }); }} aria-label="Condition operator" className="sm:w-44">
                  {OPERATORS.map((o) => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
                </Select>
                <Input value={c.value} onChange={(e) => { const next = [...s.conditions]; next[i] = { ...c, value: e.target.value }; set({ conditions: next }); }} placeholder="value" aria-label="Condition value" className="flex-1" />
                <Button type="button" variant="ghost" onClick={() => set({ conditions: s.conditions.filter((_, j) => j !== i) })} aria-label="Remove condition">
                  ✕
                </Button>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Actions <span className="font-normal text-gray-400">(only real, API-backed actions)</span></span>
            <Button type="button" variant="secondary" onClick={() => set({ actions: [...s.actions, { type: 'notification', configText: '' }] })}>
              + Add action
            </Button>
          </div>
          {s.actions.length === 0 && <p className="text-sm text-gray-400">No actions yet.</p>}
          <div className="space-y-3">
            {s.actions.map((a, i) => {
              const meta = ACTIONS.find((x) => x.value === a.type);
              return (
                <div key={i} className="rounded-lg border border-gray-200 p-3 dark:border-gray-700">
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Select value={a.type} onChange={(e) => { const next = [...s.actions]; next[i] = { ...a, type: e.target.value }; set({ actions: next }); }} aria-label="Action type" className="sm:w-72">
                      {ACTIONS.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
                    </Select>
                    <Button type="button" variant="ghost" onClick={() => set({ actions: s.actions.filter((_, j) => j !== i) })} aria-label="Remove action">
                      ✕
                    </Button>
                  </div>
                  <Field label="Config (JSON, optional)" htmlFor={`action-config-${i}`} hint={meta?.configHint}>
                    <Textarea id={`action-config-${i}`} rows={2} value={a.configText} onChange={(e) => { const next = [...s.actions]; next[i] = { ...a, configText: e.target.value }; set({ actions: next }); }} placeholder={meta?.configHint} className="font-mono text-xs" />
                  </Field>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <Checkbox checked={s.enabled} onChange={(e) => set({ enabled: e.target.checked })} /> Enabled
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <Checkbox checked={s.dryRun} onChange={(e) => set({ dryRun: e.target.checked })} />
            Dry-run mode <span className="text-gray-400">(actions are simulated, nothing changes on Gumroad)</span>
          </label>
        </div>

        <div className="flex gap-2">
          <Button type="submit" loading={saving}>{editingId ? 'Save changes' : 'Create rule'}</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

export default function Automations() {
  const { selectedAccountId } = useApp();
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [editing, setEditing] = useState<AutomationRule | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AutomationRule | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .listRules(accountQuery(selectedAccountId).account_id)
      .then(setRules)
      .catch((e: unknown) => setError(e))
      .finally(() => setLoading(false));
  }, [selectedAccountId]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleEnabled = async (r: AutomationRule) => {
    setBusy(true);
    try {
      await api.updateRule(r.id, { enabled: !r.enabled });
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (r: AutomationRule) => {
    setEditing(r);
    setBuilderOpen(true);
  };

  const builderInitial: BuilderState = editing
    ? {
        name: editing.name,
        accountId: editing.account_id ?? ALL_ACCOUNTS,
        trigger: editing.trigger,
        conditions: editing.conditions,
        actions: editing.actions.map((a) => ({ type: a.type, configText: a.config ? JSON.stringify(a.config, null, 2) : '' })),
        enabled: editing.enabled,
        dryRun: editing.dry_run,
      }
    : emptyBuilder();

  return (
    <div>
      <PageHeader
        title="Automations"
        description="Trigger → condition → action pipelines. Every action runs dry by default."
        actions={
          !builderOpen && (
            <Button onClick={() => { setEditing(null); setBuilderOpen(true); }}>+ New rule</Button>
          )
        }
      />

      {error ? <div className="mb-4"><ErrorBanner error={error} /></div> : null}

      {builderOpen && (
        <RuleBuilder
          key={editing?.id ?? 'new'}
          initial={builderInitial}
          editingId={editing?.id ?? null}
          onSaved={() => {
            setBuilderOpen(false);
            setEditing(null);
            load();
          }}
          onCancel={() => {
            setBuilderOpen(false);
            setEditing(null);
          }}
        />
      )}

      {loading && <LoadingBlock label="Loading rules…" />}

      {!loading && rules.length === 0 && (
        <EmptyState
          title="No automation rules yet"
          description="Create your first rule — e.g. send yourself a notification on every new sale over $50."
          action={!builderOpen ? <Button onClick={() => setBuilderOpen(true)}>+ New rule</Button> : undefined}
        />
      )}

      <div className="space-y-4">
        {rules.map((r) => (
          <Card key={r.id} className="p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-semibold text-gray-900 dark:text-white">{r.name}</h2>
                  <Badge tone={r.enabled ? 'green' : 'gray'}>{r.enabled ? 'Enabled' : 'Disabled'}</Badge>
                  {r.dry_run && <Badge tone="yellow">Dry-run</Badge>}
                </div>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Trigger: <span className="font-medium">{r.trigger.replace(/_/g, ' ')}</span>
                  {' · '}Conditions: {r.conditions.length}
                  {' · '}Actions: {r.actions.map((a) => a.type.replace(/_/g, ' ')).join(', ')}
                </p>
                <p className="mt-1 text-xs text-gray-400">Updated {formatDateTime(r.updated_at)}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" disabled={busy} onClick={() => toggleEnabled(r)}>
                  {r.enabled ? 'Disable' : 'Enable'}
                </Button>
                <Button variant="secondary" onClick={() => startEdit(r)}>Edit</Button>
                <Button variant="danger" onClick={() => setDeleteTarget(r)}>Delete</Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete automation rule?"
        message={<p>Delete the rule <span className="font-medium">“{deleteTarget?.name}”</span>? This cannot be undone.</p>}
        confirmLabel="Delete"
        danger
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (!deleteTarget) return;
          const id = deleteTarget.id;
          setDeleteTarget(null);
          setBusy(true);
          api
            .deleteRule(id)
            .then(load)
            .catch((e: unknown) => setError(e))
            .finally(() => setBusy(false));
        }}
      />
    </div>
  );
}
