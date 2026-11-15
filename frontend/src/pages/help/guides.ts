/** One-page guides per role (P12.6). Plain steps; no agency-specific wording. */
export interface Guide {
  key: 'agency_admin' | 'office_admin' | 'viewer';
  title: string;
  who: string;
  sections: { heading: string; steps: string[] }[];
}

export const GUIDES: Guide[] = [
  {
    key: 'agency_admin',
    title: 'Agency administrator',
    who: 'You set the agency up, approve plans, watch submissions and lock each month.',
    sections: [
      {
        heading: 'Set up (once)',
        steps: [
          'Structure: name the levels and build the office tree. Groups compare offices that are not siblings (e.g. field centers).',
          'Users: add people and give each an office and a level — admin (can edit that office and everything beneath) or read-only.',
          'Fiscal years: open the year, choose a scoring preset and the monthly cutoff day. Hover the ? next to any scoring setting for an example.',
          'Alerts and Report template: choose reminder days and the delay threshold; set the deck title, colours and logo.',
        ],
      },
      {
        heading: 'Plans',
        steps: [
          'Offices enter or import their plans and submit them. Approvals lists what is waiting; approving makes the plan the baseline.',
          'A change later is a revision: a new version that you approve again. Months already locked keep the version they were scored with.',
        ],
      },
      {
        heading: 'Every month',
        steps: [
          'Submissions shows which offices have reported. Return a report with a note if it needs changes.',
          'Lock the month when it is complete: results are frozen and become FINAL everywhere. Unlocking needs a reason and is recorded.',
          'Export to Excel or PowerPoint from the dashboard; files wait under My exports.',
        ],
      },
      {
        heading: 'Keeping track',
        steps: [
          'The audit log records every change: who, what, when, before and after.',
          'The bell shows reminders, late reports, delays and plans waiting for approval.',
        ],
      },
    ],
  },
  {
    key: 'office_admin',
    title: 'Office administrator',
    who: 'You keep your office’s plan and monthly reports up to date.',
    sections: [
      {
        heading: 'Plan',
        steps: [
          'Plans → your office → Edit. Type rows like a spreadsheet, paste from Excel, or Import from Excel using the template.',
          'Fix the messages shown under the grid (targets must add up, every activity needs a target), then Submit for approval.',
        ],
      },
      {
        heading: 'Every month, before the cutoff',
        steps: [
          'Monthly report: type what was accomplished for each activity, add remarks, and a reason for any delay.',
          'Attach supporting files (photos, scans). On a phone, open the activity from the dashboard and use Take photo.',
          'Watch the live result panel: it shows your office’s figures as you type. Submit when done; the administrator may return it with a note.',
        ],
      },
      {
        heading: 'Reminders',
        steps: [
          'The bell (and, if your agency turned it on, a daily email) reminds you before the cutoff and if accomplishments are missing.',
        ],
      },
    ],
  },
  {
    key: 'viewer',
    title: 'Read-only user',
    who: 'You follow results for your office and everything beneath it.',
    sections: [
      {
        heading: 'Dashboard',
        steps: [
          'Choose the month and the office. FINAL means the month is locked; PROVISIONAL means it can still change.',
          'The curve compares cumulative plan and accomplishment; the tiles show plan, actual, variance and status.',
          'Activities lists every activity with its progress; click one to see each month and its supporting files.',
        ],
      },
      {
        heading: 'Rankings and alerts',
        steps: [
          'Rankings orders offices under the same parent, or in a group, by accomplishment. Equal values share a rank.',
          'The bell tells you when an office you follow falls behind plan after a month is locked.',
        ],
      },
    ],
  },
];
