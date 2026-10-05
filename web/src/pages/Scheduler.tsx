import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../api/client';
import type { Job, JobExecution, JobInput, JobKind } from '../api/types';
import { ALL_ACCOUNTS, useApp } from '../context/AppContext';
import { formatDateTime, timeAgo } from '../utils';
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
} from '../components/ui';

const KINDS: { value: JobKind; label: string; scheduleHint: string }[] = [
  { value: 'once', label: 'One-time', scheduleHint: 'ISO date-time, e.g. 2026-10-06T09:00:00' },
  { value: 'recurring', label: 'Recurring', scheduleHint: 'Cron expression, e.g. */30 * * * * (every 30 min)' },
  { value: 'daily', label: 'Daily', scheduleHint: 'Time of day, e.g. 09:00' },
  { value: 'weekly', label: 'Weekly', scheduleHint: 'Day and time, e.g. MON 09:00' },
  { value: 'sync', label: 'Scheduled sync', scheduleHint: 'Cron expression for automatic Gumroad sync' },
  { value: 'automation', label: 'Automation evaluation', scheduleHint: 'Cron expression for evaluating automation rules' },
];

function statusTone(status: string): 'green' | 'yellow' | 'red' | 'gray' | 'blue' {
  if (status === 'success' || status === 'completed' || status === 'running') return 'green';
  if (status === 'failed') return 'red';
  if (status === 'dead_letter') return 'red';
  if (status === 'pending' || status === 'scheduled') return 'blue';
  if (status === 'retrying') return 'yellow';
  return 'gray';
}

function JobForm({
  initial,
  onSaved,
  onCancel,
}: {
  initial: { name: string; kind: JobKind; schedule: string; accountId: string; enabled: boolean; id: string | null };
  onSaved: () => void;
  onCancel: () => void;
}) {
  const { accounts } = useApp();
  const [name, setName] = useState(initial.name);
  const [kind, setKind] = useState<JobKind>(initial.kind);
  const [schedule, setSchedule] = useState(initial.schedule);
  const [accountId, setAccountId] = useState(initial.accountId);
  const [enabled, setEnabled] = useState(initial.enabled);
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  const kindMeta = KINDS.find((k) => k.value === kind);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const input: JobInput = {
      name: name.trim(),
      kind,
      schedule: schedule.trim() || null,
      account_id: accountId === ALL_ACCOUNTS ? null : accountId,
      enabled,
    };
    if (!input.name) {
      setError(new Error('Job name is required.'));
      return;
    }
    setSaving(true);
    try {
      if (initial.id) await api.updateJob(initial.id, input);
      else await api.createJob(input);
      onSaved();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="mb-6 p-5">
      <h2 className="text-base font-semibold text-gray-900 dark:text-white">{initial.id ? 'Edit job' : 'New job'}</h2>
      <form onSubmit={save} className="mt-4 space-y-4">
        {error ? <ErrorBanner error={error} /> : null}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Job name" htmlFor="job-name" required>
            <Input id="job-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Nightly sync" required />
          </Field>
          <Field label="Account" htmlFor="job-account" hint="Which account this job operates on.">
            <Select id="job-account" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value={ALL_ACCOUNTS}>All accounts</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Kind" htmlFor="job-kind" required>
            <Select id="job-kind" value={kind} onChange={(e) => setKind(e.target.value as JobKind)}>
              {KINDS.map((k) => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </Select>
          </Field>
          <Field label="Schedule" htmlFor="job-schedule" hint={kindMeta?.scheduleHint}>
            <Input id="job-schedule" value={schedule} onChange={(e) => setSchedule(e.target.value)} placeholder={kindMeta?.scheduleHint} />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <Checkbox checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> Enabled
        </label>
        <div className="flex gap-2">
          <Button type="submit" loading={saving}>{initial.id ? 'Save changes' : 'Create job'}</Button>
          <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        </div>
      </form>
    </Card>
  );
}

function Executions({ jobId }: { jobId: string }) {
  const [execs, setExecs] = useState<JobExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api
      .jobExecutions(jobId)
      .then(setExecs)
      .catch((e: unknown) => setError(e))
      .finally(() => setLoading(false));
  };

  useEffect(load, [jobId]);

  const retry = async (execId: string) => {
    setBusy(execId);
    try {
      await api.retryExecution(execId);
      load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <LoadingBlock label="Loading executions…" />;
  if (error) return <ErrorBanner error={error} onRetry={load} />;
  if (execs.length === 0) return <p className="text-sm text-gray-500 dark:text-gray-400">No executions yet.</p>;

  return (
    <ul className="mt-3 divide-y divide-gray-200 text-sm dark:divide-gray-800">
      {execs.map((x) => (
        <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
          <div>
            <span className="text-gray-700 dark:text-gray-300">{formatDateTime(x.started_at)}</span>
            {x.finished_at && <span className="text-gray-400"> → {formatDateTime(x.finished_at)}</span>}
            {x.error && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{x.error}</p>}
          </div>
          <div className="flex items-center gap-2">
            <Badge tone={statusTone(x.status)}>{x.status.replace(/_/g, ' ')}</Badge>
            {(x.status === 'failed' || x.status === 'dead_letter') && (
              <Button variant="secondary" disabled={busy === x.id} onClick={() => retry(x.id)}>
                {busy === x.id ? 'Retrying…' : 'Retry'}
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function Scheduler() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Job | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Job | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError(null);
    api
      .listJobs()
      .then(setJobs)
      .catch((e: unknown) => setError(e))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const act = async (key: string, fn: () => Promise<unknown>, thenLoad = true) => {
    setBusy(key);
    try {
      await fn();
      if (thenLoad) load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Scheduler"
        description="Jobs survive backend restarts. Missed runs execute once on resume."
        actions={!formOpen && <Button onClick={() => { setEditing(null); setFormOpen(true); }}>+ New job</Button>}
      />

      {error ? <div className="mb-4"><ErrorBanner error={error} /></div> : null}

      {formOpen && (
        <JobForm
          initial={
            editing
              ? { name: editing.name, kind: editing.kind, schedule: editing.schedule ?? '', accountId: editing.account_id ?? ALL_ACCOUNTS, enabled: editing.enabled, id: editing.id }
              : { name: '', kind: 'daily', schedule: '', accountId: ALL_ACCOUNTS, enabled: true, id: null }
          }
          onSaved={() => {
            setFormOpen(false);
            setEditing(null);
            load();
          }}
          onCancel={() => {
            setFormOpen(false);
            setEditing(null);
          }}
        />
      )}

      {loading && <LoadingBlock label="Loading jobs…" />}

      {!loading && jobs.length === 0 && (
        <EmptyState
          title="No jobs yet"
          description="Schedule syncs, automation evaluations, or one-time tasks."
          action={!formOpen ? <Button onClick={() => setFormOpen(true)}>+ New job</Button> : undefined}
        />
      )}

      <div className="space-y-4">
        {jobs.map((j) => (
          <Card key={j.id} className="p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-semibold text-gray-900 dark:text-white">{j.name}</h2>
                  <Badge tone="blue">{j.kind}</Badge>
                  <Badge tone={statusTone(j.status)}>{j.status.replace(/_/g, ' ')}</Badge>
                  {!j.enabled && <Badge tone="gray">Disabled</Badge>}
                </div>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  Next run: {j.next_run_at ? formatDateTime(j.next_run_at) : '—'}
                  {' · '}Last run: {j.last_run_at ? timeAgo(j.last_run_at) : 'never'}
                  {j.schedule && <> {' · '}Schedule: <span className="font-mono">{j.schedule}</span></>}
                </p>
                {j.last_error && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{j.last_error}</p>}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" disabled={busy !== null} onClick={() => act(`run-${j.id}`, () => api.runJobNow(j.id))}>
                  {busy === `run-${j.id}` ? 'Starting…' : 'Run now'}
                </Button>
                <Button variant="secondary" onClick={() => setExpanded(expanded === j.id ? null : j.id)}>
                  {expanded === j.id ? 'Hide history' : 'History'}
                </Button>
                <Button variant="secondary" disabled={busy !== null} onClick={() => act(`toggle-${j.id}`, () => api.updateJob(j.id, { enabled: !j.enabled }))}>
                  {j.enabled ? 'Disable' : 'Enable'}
                </Button>
                <Button variant="secondary" onClick={() => { setEditing(j); setFormOpen(true); }}>Edit</Button>
                <Button variant="danger" onClick={() => setDeleteTarget(j)}>Delete</Button>
              </div>
            </div>
            {expanded === j.id && <Executions jobId={j.id} />}
          </Card>
        ))}
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete job?"
        message={<p>Delete the job <span className="font-medium">“{deleteTarget?.name}”</span>? Its execution history is kept in logs.</p>}
        confirmLabel="Delete"
        danger
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (!deleteTarget) return;
          const id = deleteTarget.id;
          setDeleteTarget(null);
          void act(`delete-${id}`, () => api.deleteJob(id));
        }}
      />
    </div>
  );
}
