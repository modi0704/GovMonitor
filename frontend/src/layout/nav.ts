import type { Me } from '../api/types';

export interface NavItem {
  to: string;
  label: string;
  /** Icon name (NavIcon). */
  icon: string;
  show: (me: Me) => boolean;
  /** Hidden from the phone navigation (editing screens, D12). */
  desktopOnly?: boolean;
}

const always = () => true;
const agencyAdmin = (me: Me) => me.is_agency_admin;
const notAgencyAdmin = (me: Me) => !me.is_agency_admin;

/** Main navigation, in plain words. The agency administrator starts on the step-by-step guide; the
 * dashboard then lives at /dashboard. */
export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Step-by-step', icon: 'Steps', show: agencyAdmin },
  { to: '/', label: 'Dashboard', icon: 'Dashboard', show: notAgencyAdmin },
  { to: '/dashboard', label: 'Dashboard', icon: 'Dashboard', show: agencyAdmin },
  { to: '/rankings', label: 'Rankings', icon: 'Rankings', show: always },
  { to: '/exports', label: 'Downloads', icon: 'My exports', show: always },
  { to: '/plans', label: 'Office plans', icon: 'Plans', show: always },
  {
    to: '/reports',
    label: 'Monthly results',
    icon: 'Monthly report',
    show: always,
    desktopOnly: true,
  },
  { to: '/submissions', label: 'Who has reported', icon: 'Submissions', show: agencyAdmin },
  { to: '/structure', label: 'Offices', icon: 'Structure', show: always, desktopOnly: true },
  { to: '/groups', label: 'Office groups', icon: 'Groups', show: always, desktopOnly: true },
  { to: '/fiscal-years', label: 'Years', icon: 'Fiscal years', show: always },
  { to: '/users', label: 'Users', icon: 'Users', show: agencyAdmin, desktopOnly: true },
  { to: '/plans/approvals', label: 'Plans to approve', icon: 'Approvals', show: agencyAdmin },
  {
    to: '/settings/alerts',
    label: 'Reminders',
    icon: 'Alerts',
    show: agencyAdmin,
    desktopOnly: true,
  },
  {
    to: '/settings/report-template',
    label: 'Report look',
    icon: 'Report template',
    show: agencyAdmin,
    desktopOnly: true,
  },
  {
    to: '/audit',
    label: 'Change history',
    icon: 'Audit log',
    show: agencyAdmin,
    desktopOnly: true,
  },
  { to: '/help', label: 'Help and word list', icon: 'Help', show: always },
  { to: '/user-guide', label: 'User guide', icon: 'User guide', show: always },
];

/** Sidebar groups. ``folded`` groups start closed unless the open page is inside them. */
export const NAV_GROUPS: { title: string; labels: string[]; folded?: boolean }[] = [
  { title: 'Start here', labels: ['Step-by-step'] },
  { title: 'See results', labels: ['Dashboard', 'Rankings', 'Downloads'] },
  { title: 'Enter data', labels: ['Office plans', 'Monthly results', 'Who has reported'] },
  {
    title: 'Settings',
    labels: [
      'Offices',
      'Office groups',
      'Years',
      'Users',
      'Plans to approve',
      'Reminders',
      'Report look',
      'Change history',
    ],
    folded: true,
  },
  { title: 'Help', labels: ['User guide', 'Help and word list'] },
];
