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
          'Structure: organize your offices and name their levels. Use Groups to compare offices from different parts of the agency.',
          'Users: add people and give each an office and a level — admin (can edit that office and everything beneath) or read-only.',
          'Fiscal years: open the year, choose a scoring method, and set the report deadline. Select the question mark beside a setting for an example.',
          'Alerts: set reminders and choose how far behind plan an office must be before an alert is sent. Report template: choose the presentation title, colours, and logo.',
        ],
      },
      {
        heading: 'Plans',
        steps: [
          'Offices enter or upload their plans and submit them. Approvals shows plans waiting for review. Once approved, a plan is used to compare monthly progress.',
          'To change an approved plan, create a new draft and have it approved. Months already finalized keep their original results.',
        ],
      },
      {
        heading: 'Every month',
        steps: [
          'Submissions shows which offices have reported. Return a report with a note if it needs changes.',
          'After review, lock the month to make its results final and stop changes. Reopening a month requires a reason that is saved in the audit log.',
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
        heading: 'Every month, before the deadline',
        steps: [
          'Monthly report: type what was accomplished for each activity, add remarks, and a reason for any delay.',
          'Attach supporting files (photos, scans). On a phone, open the activity from the dashboard and use Take photo.',
          'Watch the live result panel: it shows your office’s figures as you type. Submit when done; the administrator may return it with a note.',
        ],
      },
      {
        heading: 'Reminders',
        steps: [
          'The bell reminds you about report deadlines and missing accomplishments. Your agency may also send a daily email summary.',
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
          'Choose the month and office. FINAL means the figures are locked. NOT FINAL means reports may still change.',
          'The chart compares planned and completed work since the year began. The cards show progress, the gap from plan, status, and funds used.',
          'Activities lists every activity with its progress; click one to see each month and its supporting files.',
        ],
      },
      {
        heading: 'Rankings and alerts',
        steps: [
          'Rankings compares offices reporting to the same office, or offices in a chosen group. Offices with equal results share a rank.',
          'The bell tells you when an office you follow falls behind plan after a month is locked.',
        ],
      },
    ],
  },
];
