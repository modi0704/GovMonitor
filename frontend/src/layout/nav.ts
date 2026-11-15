import type { Me } from '../api/types';

export interface NavItem {
  to: string;
  label: string;
  show: (me: Me) => boolean;
}

const always = () => true;
const agencyAdmin = (me: Me) => me.is_agency_admin;

/** Main navigation. Later phases add dashboard, plans, reports, exports. */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', show: always },
  { to: '/rankings', label: 'Rankings', show: always },
  { to: '/reports', label: 'Monthly report', show: always },
  { to: '/submissions', label: 'Submissions', show: agencyAdmin },
  { to: '/plans', label: 'Plans', show: always },
  { to: '/plans/approvals', label: 'Approvals', show: agencyAdmin },
  { to: '/fiscal-years', label: 'Fiscal years', show: always },
  { to: '/structure', label: 'Structure', show: always },
  { to: '/groups', label: 'Groups', show: always },
  { to: '/users', label: 'Users', show: agencyAdmin },
  { to: '/audit', label: 'Audit log', show: agencyAdmin },
];
