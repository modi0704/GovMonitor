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
