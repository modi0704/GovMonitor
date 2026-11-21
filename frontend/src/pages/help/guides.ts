/** One-page guides per role (P12.6). Plain steps; no agency-specific wording. */
export interface Guide {
  key: 'agency_admin' | 'office_admin' | 'viewer';
  title: string;
  who: string;
  sections: { heading: string; steps: string[] }[];
}

/** Plain meanings of the words the app and the reports use. */
export const WORDS: { word: string; meaning: string }[] = [
  {
    word: 'Plan',
    meaning:
      'What an office said it would do this year: its activities, how many each month, and their cost.',
  },
  {
    word: 'Activity (PPA)',
    meaning:
      'One piece of planned work — a program, project or activity — with a yearly target number.',
  },
  { word: 'Actual', meaning: 'What the office really did, as reported each month.' },
  {
    word: 'Plan % / Actual % (total so far)',
    meaning:
      'How much of the whole year’s work should be done by this month, and how much is done. Bigger, costlier activities count for more.',
  },
  {
    word: 'Gap (variance)',
    meaning: 'Actual minus plan. Below zero means the office is behind; above zero means ahead.',
  },
  {
    word: 'Status',
    meaning: 'Ahead (ADVANCED), on plan (ON-TIME) or behind plan (DELAYED), from the gap.',
  },
  {
    word: 'Output indicator (output target)',
    meaning:
      'A result counted over the year, for example “number of teachers trained”, with a yearly target.',
  },
  {
    word: 'Output targets reached',
    meaning: 'The share of the year’s output targets reached so far, averaged over the indicators.',
  },
  {
    word: 'Funds remaining',
    meaning:
      'The budget not yet used, estimated from the work done (or from the amounts you entered).',
  },
  {
    word: 'S-curve',
    meaning:
      'A line chart of plan and actual (total so far) month by month. The space between the lines is the gap.',
  },
  {
    word: 'Mark as final (plan)',
    meaning: 'Confirms an office’s plan so it is used for the monthly results.',
  },
  { word: 'Submit report', meaning: 'Marks an office’s month as done.' },
  {
    word: 'Close the month',
    meaning:
      'Makes a month’s figures final so they cannot change by mistake. Reopening needs a reason, which is recorded.',
  },
  {
    word: 'Proof (MOV)',
    meaning: 'Supporting files such as photos or signed reports attached to an activity.',
  },
  { word: 'Change history (audit log)', meaning: 'A record of who changed what and when.' },
];

export const GUIDES: Guide[] = [
  {
    key: 'agency_admin',
    title: 'Monitoring administrator',
    who: 'You collect the figures from the offices you handle and enter everything yourself. Step-by-step (your start page) walks you through it with a progress bar.',
    sections: [
      {
        heading: 'Once: set up',
        steps: [
          'Step 1 — Offices: list the offices you monitor and which office is under which. Office groups let you compare offices from different parts of the agency (for example, island and mainland offices).',
          'Step 2 — Years: add the year you monitor. The app creates its twelve months.',
          'Optional: Users lets you give other people access (to view, or to enter their own office’s figures). You do not need it if you enter everything yourself.',
        ],
      },
      {
        heading: 'Once a year: plans',
        steps: [
          'Step 3 — Office plans: collect each office’s work and financial plan. For each office, press Start plan, type the activities, their target number per month and cost, and the output targets. You can also upload a filled-in Excel template.',
          'When an office’s plan is complete, press Mark as final. Only final plans are used for the monthly results. To change a final plan later, revise it; closed months keep their results.',
        ],
      },
      {
        heading: 'Every month',
        steps: [
          'Step 4 — Monthly results: collect each office’s accomplishment report. Open the office, type what it did, give a short reason for anything behind plan, save, then Submit report to mark it as done.',
          'Step 5 — Check and close: look over the dashboard and rankings. When the figures are right, close the month so they become final.',
          'Step 6 — Download: the monthly report (Excel or PowerPoint), or the over-all performance presentation for the year. Files stay under Downloads.',
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
          'Office plans → your office → Edit. Type rows like a spreadsheet, paste from Excel, or Import from Excel using the template.',
          'Fix the messages shown under the grid (targets must add up, every activity needs a target), then Submit for approval.',
        ],
      },
      {
        heading: 'Every month, before the deadline',
        steps: [
          'Monthly results: type what was accomplished for each activity, add remarks, and a reason for any delay.',
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
          'Choose the month and office. FINAL means the month is closed. PROVISIONAL means the figures may still change.',
          'The chart compares planned and completed work since the year began. The cards show progress, the gap from plan, status, and funds used.',
          'Activities lists every activity with its progress; click one to see each month and its supporting files.',
        ],
      },
      {
        heading: 'Rankings and alerts',
        steps: [
          'Rankings compares offices reporting to the same office, or offices in a chosen group. Offices with equal results share a rank.',
          'The bell tells you when an office you follow falls behind plan after a month is closed.',
        ],
      },
    ],
  },
];
