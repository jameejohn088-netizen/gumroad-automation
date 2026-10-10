/**
 * Typed API client for the Gumroad Automation backend.
 * Base URL comes from VITE_API_URL (default http://localhost:8000/api/v1).
 * No Gumroad token ever reaches the browser — all Gumroad calls happen server-side.
 */
import type {
  ActionResult,
  ActivityLog,
  AppNotification,
  AutomationRule,
  AutomationRuleInput,
  DashboardData,
  ErrorLog,
  GumroadAccount,
  Job,
  JobExecution,
  JobInput,
  License,
  Membership,
  Paginated,
  Product,
  Sale,
  Customer,
  Subscriber,
  SyncHistoryItem,
  TokenPair,
  User,
} from './types';

const RAW_BASE = import.meta.env.VITE_API_URL as string | undefined;
// When served from the backend (same origin), talk to that origin's /api/v1
// automatically — this survives tunnel URL rotations without a rebuild.
const SAME_ORIGIN_BASE =
  typeof window !== 'undefined' ? `${window.location.origin}/api/v1` : '';
export const API_BASE = (RAW_BASE && RAW_BASE.trim() ? RAW_BASE : (SAME_ORIGIN_BASE || 'http://localhost:8000/api/v1')).replace(
  /\/+$/,
  '',
);

export class ApiError extends Error {
  status: number;
  correlationId: string | null;
  constructor(status: number, message: string, correlationId: string | null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.correlationId = correlationId;
  }
}

const ACCESS_KEY = 'ga_access_token';
const REFRESH_KEY = 'ga_refresh_token';

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}
function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}
export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}
export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;
export function setUnauthorizedHandler(h: UnauthorizedHandler | null): void {
  onUnauthorized = h;
}

/** Single-flight refresh so concurrent 401s only refresh once. */
let refreshPromise: Promise<boolean> | null = null;
async function tryRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    const rt = getRefreshToken();
    if (!rt) return false;
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: rt }),
      });
      if (!res.ok) return false;
      const data = (await res.json()) as TokenPair;
      if (!data.access_token || !data.refresh_token) return false;
      setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
    }
  })();
  const ok = await refreshPromise;
  refreshPromise = null;
  return ok;
}

async function parseError(res: Response): Promise<{ message: string; correlationId: string | null }> {
  const headerCid = res.headers.get('x-correlation-id') ?? res.headers.get('x-request-id');
  let message = `Request failed (${res.status})`;
  let cid: string | null = headerCid;
  try {
    const data = (await res.json()) as Record<string, unknown>;
    if (typeof data.detail === 'string') message = data.detail;
    else if (typeof data.message === 'string') message = data.message;
    else if (typeof data.error === 'string') message = data.error;
    if (typeof data.correlation_id === 'string') cid = data.correlation_id;
  } catch {
    /* non-JSON error body */
  }
  return { message, correlationId: cid };
}

interface FetchOpts {
  auth: boolean;
  retried: boolean;
}

async function fetchWithAuth(url: string, init: RequestInit, opts: FetchOpts): Promise<Response> {
  const headers = new Headers(init.headers);
  if (opts.auth) {
    const token = getAccessToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_BASE}. Is the backend running?`, null);
  }
  if (res.status === 401 && opts.auth && !opts.retried) {
    if (await tryRefresh()) {
      return fetchWithAuth(url, init, { auth: true, retried: true });
    }
    clearTokens();
    if (onUnauthorized) onUnauthorized();
    throw new ApiError(401, 'Your session expired. Please log in again.', null);
  }
  return res;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  /** default true; false for login/signup (no token attached, no auto-logout on 401) */
  auth?: boolean;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const url = new URL(API_BASE + path);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, auth = true } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const res = await fetchWithAuth(
    buildUrl(path, query),
    { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined },
    { auth, retried: false },
  );
  if (!res.ok) {
    const e = await parseError(res);
    throw new ApiError(res.status, e.message, e.correlationId);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function downloadFile(path: string, query: RequestOptions['query'], filename: string): Promise<void> {
  const res = await fetchWithAuth(buildUrl(path, query), { method: 'GET' }, { auth: true, retried: false });
  if (!res.ok) {
    const e = await parseError(res);
    throw new ApiError(res.status, e.message, e.correlationId);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export interface ListParams {
  account_id?: string;
  q?: string;
  page?: number;
  per_page?: number;
}

/** All backend endpoints, typed. */
export const api = {
  // ---- Auth ----
  signup: (name: string, email: string, password: string) =>
    request<{ message?: string }>('/auth/signup', { method: 'POST', body: { name, email, password }, auth: false }),
  login: (email: string, password: string) =>
    request<TokenPair>('/auth/login', { method: 'POST', body: { email, password }, auth: false }),
  refresh: (refresh_token: string) =>
    request<TokenPair>('/auth/refresh', { method: 'POST', body: { refresh_token }, auth: false }),
  logout: (refresh_token: string) =>
    request<void>('/auth/logout', { method: 'POST', body: { refresh_token } }),
  forgotPassword: (email: string) =>
    request<{ message: string }>('/auth/forgot-password', { method: 'POST', body: { email }, auth: false }),
  resetPassword: (token: string, new_password: string) =>
    request<{ message: string }>('/auth/reset-password', {
      method: 'POST',
      body: { token, new_password },
      auth: false,
    }),
  verifyEmail: (token: string) =>
    request<{ message: string }>('/auth/verify-email', { method: 'POST', body: { token }, auth: false }),
  me: () => request<User>('/auth/me'),
  updateMe: (data: { name?: string }) => request<User>('/auth/me', { method: 'PATCH', body: data }),
  changePassword: (current_password: string, new_password: string) =>
    request<{ message: string }>('/auth/change-password', {
      method: 'POST',
      body: { current_password, new_password },
    }),

  // ---- Gumroad accounts ----
  listAccounts: () => request<GumroadAccount[]>('/gumroad-accounts'),
  createAccount: (name: string) =>
    request<GumroadAccount>('/gumroad-accounts', { method: 'POST', body: { name } }),
  getAccount: (id: string) => request<GumroadAccount>(`/gumroad-accounts/${id}`),
  updateAccount: (id: string, data: { name?: string }) =>
    request<GumroadAccount>(`/gumroad-accounts/${id}`, { method: 'PATCH', body: data }),
  deleteAccount: (id: string) => request<void>(`/gumroad-accounts/${id}`, { method: 'DELETE' }),
  connectManual: (id: string, access_token: string) =>
    request<GumroadAccount>(`/gumroad-accounts/${id}/connect-manual`, {
      method: 'POST',
      body: { access_token },
    }),
  disconnectAccount: (id: string) =>
    request<GumroadAccount>(`/gumroad-accounts/${id}/disconnect`, { method: 'POST' }),
  reconnectAccount: (id: string) =>
    request<GumroadAccount>(`/gumroad-accounts/${id}/reconnect`, { method: 'POST' }),
  enableAccount: (id: string) => request<GumroadAccount>(`/gumroad-accounts/${id}/enable`, { method: 'POST' }),
  disableAccount: (id: string) => request<GumroadAccount>(`/gumroad-accounts/${id}/disable`, { method: 'POST' }),
  syncAccount: (id: string) => request<{ job_id: string }>(`/gumroad-accounts/${id}/sync`, { method: 'POST' }),
  syncHistory: (id: string) => request<SyncHistoryItem[]>(`/gumroad-accounts/${id}/sync-history`),

  // ---- Dashboard ----
  dashboard: (account_id?: string) =>
    request<DashboardData>('/dashboard', { query: { account_id } }),

  // ---- Catalog ----
  products: (p: ListParams = {}) => request<Paginated<Product>>('/products', { query: { ...p } }),
  sales: (p: ListParams = {}) => request<Paginated<Sale>>('/sales', { query: { ...p } }),
  customers: (p: ListParams = {}) => request<Paginated<Customer>>('/customers', { query: { ...p } }),
  subscribers: (p: ListParams = {}) => request<Paginated<Subscriber>>('/subscribers', { query: { ...p } }),
  licenses: (p: ListParams = {}) => request<Paginated<License>>('/licenses', { query: { ...p } }),
  memberships: (p: ListParams = {}) => request<Paginated<Membership>>('/memberships', { query: { ...p } }),

  // ---- Sale actions (dry-run by default) ----
  refundSale: (saleId: string, dry_run: boolean) =>
    request<ActionResult>(`/sales/${saleId}/refund`, { method: 'POST', body: { dry_run } }),
  markShipped: (saleId: string, dry_run: boolean) =>
    request<ActionResult>(`/sales/${saleId}/mark-shipped`, { method: 'POST', body: { dry_run } }),
  exportSalesCsv: (account_id?: string) =>
    downloadFile('/export/sales.csv', { account_id }, `sales-${new Date().toISOString().slice(0, 10)}.csv`),

  // ---- Automation rules ----
  listRules: (account_id?: string) =>
    request<AutomationRule[]>('/automation-rules', { query: { account_id } }),
  createRule: (input: AutomationRuleInput) =>
    request<AutomationRule>('/automation-rules', { method: 'POST', body: input }),
  getRule: (id: string) => request<AutomationRule>(`/automation-rules/${id}`),
  updateRule: (id: string, input: Partial<AutomationRuleInput>) =>
    request<AutomationRule>(`/automation-rules/${id}`, { method: 'PATCH', body: input }),
  deleteRule: (id: string) => request<void>(`/automation-rules/${id}`, { method: 'DELETE' }),

  // ---- Scheduler ----
  listJobs: () => request<Job[]>('/jobs'),
  createJob: (input: JobInput) => request<Job>('/jobs', { method: 'POST', body: input }),
  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  updateJob: (id: string, input: Partial<JobInput>) =>
    request<Job>(`/jobs/${id}`, { method: 'PATCH', body: input }),
  deleteJob: (id: string) => request<void>(`/jobs/${id}`, { method: 'DELETE' }),
  jobExecutions: (id: string) => request<JobExecution[]>(`/jobs/${id}/executions`),
  runJobNow: (id: string) => request<JobExecution>(`/jobs/${id}/run-now`, { method: 'POST' }),
  retryExecution: (id: string) => request<JobExecution>(`/executions/${id}/retry`, { method: 'POST' }),

  // ---- Notifications & logs ----
  notifications: () => request<AppNotification[]>('/notifications'),
  markNotificationRead: (id: string) =>
    request<AppNotification>(`/notifications/${id}/read`, { method: 'POST' }),
  activityLogs: (p: ListParams = {}) => request<Paginated<ActivityLog>>('/activity-logs', { query: { ...p } }),
  errorLogs: (p: ListParams = {}) => request<Paginated<ErrorLog>>('/error-logs', { query: { ...p } }),
};
