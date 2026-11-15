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
  is_agency_admin: boolean;
  agency: {
    id: string;
    name: string;
    code: string;
    timezone: string;
    fiscal_year_start_month: number;
    logo: boolean;
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
