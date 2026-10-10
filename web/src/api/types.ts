/** TypeScript types matching the backend API contract (base /api/v1). */

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

export type AccountStatus = 'connected' | 'needs_reconnect' | 'error' | 'disabled';

export interface GumroadAccount {
  id: string;
  name: string;
  status: AccountStatus;
  last_sync_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SyncHistoryItem {
  id: string;
  account_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  error: string | null;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface Product {
  id: string;
  account_id: string;
  gumroad_id: string;
  name: string;
  price_cents: number;
  currency: string;
  published: boolean;
  sales_count: number;
  thumbnail_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface Sale {
  id: string;
  account_id: string;
  gumroad_id: string;
  product_name: string | null;
  email: string | null;
  amount_cents: number;
  currency: string;
  refunded: boolean;
  shipped: boolean;
  is_subscription: boolean;
  created_at: string;
}

export interface Customer {
  id: string;
  account_id: string;
  email: string;
  name: string | null;
  first_purchase_at: string | null;
  total_spent_cents: number;
  purchase_count: number;
  created_at: string;
  updated_at: string;
}

export interface Subscriber {
  id: string;
  account_id: string;
  gumroad_id: string;
  email: string | null;
  product_name: string | null;
  status: string;
  created_at: string;
}

export interface License {
  id: string;
  account_id: string;
  gumroad_id: string;
  key: string | null;
  product_name: string | null;
  email: string | null;
  uses: number | null;
  enabled: boolean;
  created_at: string;
}

export interface Membership {
  id: string;
  account_id: string;
  product_name: string;
  tier_name: string | null;
  subscriber_count: number;
  status: string;
  recurrence: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardData {
  revenue_cents: number;
  sales_count: number;
  customers_count: number;
  subscribers_count: number;
  products_count: number;
  recent_sales: Sale[];
}

export interface AnalyticsProduct {
  product_id: string;
  name: string;
  price_cents: number;
  permalink: string | null;
  published: boolean;
  gross_cents: number;
  sales_count: number;
}

export interface AnalyticsDay {
  date: string;
  gross_cents: number;
  sales_count: number;
}

export interface AnalyticsData {
  gross_cents: number;
  refunded_cents: number;
  net_cents: number;
  sales_count: number;
  refunded_count: number;
  disputed_count: number;
  per_product: AnalyticsProduct[];
  daily_trend: AnalyticsDay[];
  no_sale_products: { product_id: string; name: string }[];
  range: { preset: string; start: string | null; end: string | null };
}

export type RuleTrigger =
  | 'new_sale'
  | 'refund'
  | 'new_subscriber'
  | 'subscription_cancelled'
  | 'subscription_ended'
  | 'product_change'
  | 'schedule'
  | 'sales_threshold';

export interface RuleCondition {
  field: string;
  operator: string;
  value: string;
}

export interface RuleAction {
  type: string;
  config?: Record<string, string>;
}

export interface AutomationRule {
  id: string;
  account_id: string | null;
  name: string;
  trigger: RuleTrigger;
  conditions: RuleCondition[];
  actions: RuleAction[];
  enabled: boolean;
  dry_run: boolean;
  created_at: string;
  updated_at: string;
}

export interface AutomationRuleInput {
  name: string;
  account_id?: string | null;
  trigger: RuleTrigger;
  conditions: RuleCondition[];
  actions: RuleAction[];
  enabled: boolean;
  dry_run: boolean;
}

export type JobKind = 'once' | 'recurring' | 'daily' | 'weekly' | 'sync' | 'automation';

export interface Job {
  id: string;
  account_id: string | null;
  name: string;
  kind: JobKind;
  schedule: string | null;
  enabled: boolean;
  status: string;
  next_run_at: string | null;
  last_run_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobInput {
  name: string;
  account_id?: string | null;
  kind: JobKind;
  schedule?: string | null;
  enabled: boolean;
}

export interface JobExecution {
  id: string;
  job_id: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  error: string | null;
}

export interface AppNotification {
  id: string;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
}

export interface ActivityLog {
  id: string;
  account_id: string | null;
  action: string;
  message: string;
  created_at: string;
}

export interface ErrorLog {
  id: string;
  message: string;
  correlation_id: string | null;
  context: string | null;
  created_at: string;
}

export interface ActionResult {
  success: boolean;
  message: string;
  dry_run: boolean;
}
