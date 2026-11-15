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
