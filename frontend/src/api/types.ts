export interface RoleRef {
  id: string;
  office_id: string;
  level: 'admin' | 'read_only';
}

export interface Me {
  id: string;
  email: string;
  full_name: string;
  must_change_password: boolean;
  has_2fa: boolean;
  email_opt_out?: boolean;
  is_agency_admin: boolean;
  agency: {
    id: string;
    name: string;
    code: string;
    timezone: string;
    fiscal_year_start_month: number;
    logo: boolean;
    setup_complete: boolean;
  };
  roles: RoleRef[];
}

export type LoginResponse = { status: 'ok'; me: Me } | { status: '2fa_required' };

export interface PlatformAgency {
  id: string;
  name: string;
  code: string;
  status: 'active' | 'suspended';
  fiscal_year_start_month: number;
  timezone: string;
  created_at: string;
}

export interface Level {
  id: string;
  depth: number;
  name: string;
  office_count: number;
}

export interface OfficeRow {
  id: string;
  parent_id: string | null;
  code: string;
  name: string;
  depth: number;
  level: { id: string; name: string; depth: number };
  sort_order: number;
  is_active: boolean;
  can_edit: boolean;
}

export interface OfficeGroup {
  id: string;
  name: string;
  description: string;
  sort_order: number;
  members: { id: string; code: string; name: string; is_active: boolean }[];
}

export interface Assignment {
  id: string;
  office: { id: string; code: string; name: string };
  level: 'admin' | 'read_only';
  is_root: boolean;
}

export interface UserRow {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  has_2fa: boolean;
  must_change_password: boolean;
  locked: boolean;
  last_login_at: string | null;
  created_at: string;
  assignments: Assignment[];
  is_agency_admin: boolean;
  temporary_password?: string;
}

export interface ScopeOffice {
  id: string;
  code: string;
  name: string;
  depth: number;
  can_edit: boolean;
}

export interface AuditRow {
  id: number;
  at: string;
  actor_type: string;
  actor_id: string | null;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string;
  office_id: string | null;
  ip: string | null;
  changed: string[];
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  user_agent?: string;
  request_id?: string;
}

export interface AuditPage {
  results: AuditRow[];
  next_before: number | null;
  actions: string[];
  entity_types: string[];
}

export interface Period {
  id: string;
  month_index: number;
  start_date: string;
  end_date: string;
  cutoff_at: string;
  status: 'open' | 'locked';
  locked_at: string | null;
}

export interface FiscalYear {
  id: string;
  label: string;
  start_date: string;
  end_date: string;
  status: 'draft' | 'open' | 'closed';
  preset: string;
  profile_id: string;
  periods?: Period[];
}

export interface ScoringProfile {
  id: string;
  fiscal_year_id: string;
  version: number;
  locked_months: number;
  preset: string;
  weighting: 'cost_share' | 'equal' | 'manual';
  cap_at_100: boolean;
  on_time_tolerance: string;
  label_ahead: string;
  label_on_time: string;
  label_delayed: string;
  rollup: 'budget_weighted' | 'simple_average';
  indicator_weighting: 'equal' | 'manual';
  indicator_rollup: 'all_indicators' | 'office_scores';
  ranking_metric: 'cumulative_actual' | 'variance' | 'actual_over_plan';
  mov_required: boolean;
  auto_lock: boolean;
  cutoff_day: number;
  show_actual_amounts: boolean;
}

export interface Preset {
  name: string;
  description: string;
  settings: Record<string, unknown>;
}

export interface PlanSummary {
  id: string;
  office: { id: string; code: string; name: string };
  fiscal_year: { id: string; label: string };
  version: number;
  status: 'draft' | 'submitted' | 'approved' | 'superseded';
  approved_budget: string | null;
  planned_cost: string;
  submitted_at: string | null;
  submitted_by: string | null;
  approved_at: string | null;
  approved_by: string | null;
  updated_at: string;
  can_edit: boolean;
  office_editable: boolean;
}

export interface Attachment {
  id: string;
  target_type: 'activity_actual' | 'indicator_actual';
  target_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  description: string;
  uploaded_by: string | null;
  uploaded_at: string;
  download_url: string;
}

export interface Headline {
  cum_plan: string;
  cum_actual: string;
  periodic_plan: string;
  periodic_actual: string;
  variance: string;
  status: string;
  funds_total: string;
  funds_used_est: string;
  funds_used_actual: string | null;
  funds_remaining: string;
  indicator_score: string | null;
}

export interface ReportActivity {
  lineage_id: string;
  code: string;
  title: string;
  unit: string;
  measure_type: 'quantity' | 'money' | 'recurring';
  annual_target: string;
  owner_office: { id: string; code: string };
  implementing_office: { id: string; code: string };
  target_month: string;
  cum_target: string;
  prev_cum_actual: string;
  actual: string | null;
  actual_amount: string | null;
  remarks: string;
  delay_reason: string;
  attachments: number;
  planned_ratio: string;
  actual_ratio: string;
  behind: boolean;
  no_target: boolean;
  editable: boolean;
}

export interface ReportIndicator {
  lineage_id: string;
  code: string;
  name: string;
  unit: string;
  annual_target: string;
  aggregation: 'sum' | 'last';
  target_month: string;
  actual: string | null;
  remarks: string;
  attachments: number;
}

export interface MonthReport {
  office: { id: string; code: string; name: string };
  view: 'owner' | 'implementing';
  has_plan: boolean;
  plan_id: string | null;
  period: {
    id: string;
    month_index: number;
    start_date: string;
    cutoff_at: string;
    status: 'open' | 'locked';
    fiscal_year: { id: string; label: string };
  };
  submission: {
    status: 'draft' | 'submitted' | 'returned' | 'locked';
    submitted_at?: string | null;
    submitted_by?: string | null;
    returned_at?: string | null;
    returned_by?: string | null;
    return_note?: string;
  };
  can_submit: boolean;
  can_return: boolean;
  mov_required: boolean;
  show_amounts: boolean;
  activities: ReportActivity[];
  indicators: ReportIndicator[];
  result: Headline | null;
}
