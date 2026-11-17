/** Display names only. Stored scoring choices and calculations keep their existing keys. */
const METHODS: Record<string, { name: string; description: string }> = {
  workbook_compatible: {
    name: 'Excel method',
    description:
      'Use the same scoring method as the Excel monitoring workbook. Activities count according to cost, and scores can exceed 100%.',
  },
  capped_with_tolerance: {
    name: '100% limit with an on-time allowance',
    description:
      'Count activities by cost, limit progress to 100%, and treat a gap of up to 2 percentage points above or below plan as on time.',
  },
  custom: {
    name: 'Your own settings',
    description: 'Use the scoring choices selected by your agency.',
  },
};

export const scoringMethodName = (name: string) => METHODS[name]?.name ?? 'Agency scoring method';
export const scoringMethodDescription = (name: string) =>
  METHODS[name]?.description ?? 'Use the scoring choices selected by your agency.';
