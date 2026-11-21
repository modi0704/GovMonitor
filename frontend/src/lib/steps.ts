/** The monitoring routine, in order. The administrator collects the figures from the offices and
 * enters everything; these steps say what to collect, where to enter it and when it is done. */

export type StepKey = 'offices' | 'year' | 'plans' | 'results' | 'review' | 'report';

export interface StepInfo {
  key: StepKey;
  title: string;
  /** Short label under the progress bar. */
  short: string;
  /** One sentence: what this step is for. */
  why: string;
  /** What to ask the offices for before starting this step. */
  gather: string[];
  /** Pages that belong to this step (the guide bar shows on them). */
  paths: string[];
}

export const STEPS: StepInfo[] = [
  {
    key: 'offices',
    title: 'Add your offices',
    short: 'Offices',
    why: 'List every office you monitor, for example your divisions and provincial offices, so each one gets its own plan and results.',
    gather: [
      'The names of the offices you monitor',
      'Which office is under which (for example, divisions under a service)',
    ],
    paths: ['/structure', '/groups', '/setup'],
  },
  {
    key: 'year',
    title: 'Set up the year',
    short: 'Year',
    why: 'Create the year you are monitoring. The app makes its twelve months for you.',
    gather: ['The year to monitor (for example 2026)'],
    paths: ['/fiscal-years'],
  },
  {
    key: 'plans',
    title: "Enter each office's plan",
    short: 'Plans',
    why: 'For every office, type in what it plans to do this year: its activities, how many it will do each month, their cost, and its output targets.',
    gather: [
      "Each office's work and financial plan for the year",
      'For each activity: the target number per month and the cost',
      'The output targets (indicators) and their yearly targets',
    ],
    paths: ['/plans'],
  },
  {
    key: 'results',
    title: 'Enter the monthly results',
    short: 'Monthly results',
    why: 'Each month, type in what every office actually did. When an office is complete, mark it as done.',
    gather: [
      "Each office's accomplishment report for the month",
      'A short reason for any activity that is behind',
      'Proof such as photos or signed reports, if your agency asks for it',
    ],
    paths: ['/reports', '/submissions'],
  },
  {
    key: 'review',
    title: 'Check and close the month',
    short: 'Check & close',
    why: 'Look over the dashboard. When the figures are right, close the month so they become final and cannot change by mistake.',
    gather: [],
    paths: ['/dashboard', '/rankings'],
  },
  {
    key: 'report',
    title: 'Download the report',
    short: 'Report',
    why: 'Download the monthly report, or the over-all performance presentation for the year, ready to show.',
    gather: [],
    paths: ['/exports'],
  },
];

export const stepIndex = (key: StepKey) => STEPS.findIndex((s) => s.key === key);

export function stepForPath(pathname: string): StepInfo | undefined {
  return STEPS.find((s) => s.paths.some((p) => pathname === p || pathname.startsWith(`${p}/`)));
}

/** Plain words for the statuses the steps show. */
export const PLAN_WORD: Record<string, string> = {
  none: 'Not started',
  draft: 'Being entered',
  submitted: 'Waiting for approval',
  approved: 'Final',
};

export const MONTH_WORD: Record<string, string> = {
  not_started: 'Not started',
  draft: 'Being entered',
  returned: 'Needs changes',
  submitted: 'Done',
  locked: 'Closed',
};
