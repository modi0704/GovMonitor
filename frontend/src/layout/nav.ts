import type { Me } from '../api/types';

export interface NavItem {
  to: string;
  label: string;
  show: (me: Me) => boolean;
  /** Hidden from the phone navigation (editing screens, D12). */
  desktopOnly?: boolean;
}

const always = () => true;
const agencyAdmin = (me: Me) => me.is_agency_admin;

/** Main navigation. */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', show: always },
  { to: '/rankings', label: 'Rankings', show: always },
  { to: '/reports', label: 'Monthly report', show: always, desktopOnly: true },
  { to: '/submissions', label: 'Submissions', show: agencyAdmin },
  { to: '/plans', label: 'Plans', show: always },
  { to: '/plans/approvals', label: 'Approvals', show: agencyAdmin },
  { to: '/fiscal-years', label: 'Fiscal years', show: always },
  { to: '/structure', label: 'Structure', show: always, desktopOnly: true },
  { to: '/groups', label: 'Groups', show: always, desktopOnly: true },
  { to: '/users', label: 'Users', show: agencyAdmin, desktopOnly: true },
  { to: '/exports', label: 'My exports', show: always },
  { to: '/settings/alerts', label: 'Alerts', show: agencyAdmin, desktopOnly: true },
  {
    to: '/settings/report-template',
    label: 'Report template',
    show: agencyAdmin,
    desktopOnly: true,
  },
  { to: '/audit', label: 'Audit log', show: agencyAdmin, desktopOnly: true },
];
