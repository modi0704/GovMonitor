import type { Headline } from '../../api/types';

export interface OfficeRef {
  id: string;
  code: string;
  name: string;
  depth: number;
  is_active: boolean;
}

export interface ResultSummary {
  cum_plan: string;
  cum_actual: string;
  variance: string;
  status: string;
  status_kind: string;
  funds_total: string;
  rank_sibling: number | null;
}

export interface RankingSet {
  set: { kind: 'children' | 'group'; id: string; name: string };
  rows: {
    office: OfficeRef;
    rank: number | null;
    value: string | null;
    result: ResultSummary | null;
  }[];
}

export interface Dashboard {
  office: OfficeRef & { has_children: boolean; ancestors: OfficeRef[] };
  period: {
    id: string;
    month_index: number;
    start_date: string;
    status: string;
    fiscal_year: { id: string; label: string };
  };
  months: string[];
  view: 'owner' | 'implementing';
  views: ('owner' | 'implementing')[];
  final: boolean;
  label: 'FINAL' | 'PROVISIONAL';
  has_result: boolean;
  headline: (Headline & { status_kind?: string; final?: boolean }) | null;
  rank_sibling: number | null;
  plan_version: number | null;
  series: { cum_plan: string[]; cum_actual: (string | null)[] } | null;
  indicators: {
    lineage_id: string;
    code: string;
    name: string;
    unit: string;
    annual_target: string;
    actual_to_date: string | null;
    rate: string;
  }[];
  children: { office: OfficeRef; result: ResultSummary | null }[];
  rankings: RankingSet[];
}

export interface DashActivity {
  lineage_id: string;
  code: string;
  title: string;
  unit: string;
  owner_office_code: string;
  implementing_office_code: string;
  annual_target: string;
  weight: string;
  planned_ratio: string;
  actual_ratio: string;
  variance: string;
  status_kind: 'ahead' | 'on_time' | 'delayed' | 'no_target' | null;
  cum_target: string;
  cum_actual: string;
  delay_reason: string;
  no_target: boolean;
}
