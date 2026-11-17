/** Longer explanations, with small examples, for every scoring setting (P12.6). */
export const SCORING_TIPS: Record<string, string> = {
  preset:
    'Choose a starting method to fill in the settings below. Excel method follows the agency’s monitoring workbook. You can then adjust individual choices for your agency.',
  weighting:
    'For activities costing 600,000, 300,000 and 100,000, cost-based scoring assigns 60%, 30% and 10% of the office score. Equal shares give each activity one third. Shares entered by hand must total 100%.',
  cap_at_100:
    'Example: plan 10, done 12. Without the limit, the activity scores 120%. With the limit, it scores 100%, so extra work on one activity cannot hide delays in others.',
  on_time_tolerance:
    'With a 2-point allowance, 48.5% completed against a 50% plan is on time; 47% is behind. Compare work completed since the year began with the plan for the same months.',
  labels:
    'These words appear on dashboards and downloaded reports for offices ahead of, on, or behind plan. Changing the words does not change any figures.',
  rollup:
    'Two divisions have budgets of 1,000,000 and 3,000,000, with progress of 78% and 90%. Combining them by budget gives their supervising office 87%. Giving both equal shares gives 84%.',
  indicator_weighting:
    'An indicator tracks a result, such as people trained. Give each indicator an equal share of the score, or enter the share for each one in the plan. Entered shares must total 100%.',
  indicator_rollup:
    'Average all indicators from the offices below, or average each office’s indicator score. The second choice gives offices an equal say even when they track different numbers of indicators.',
  ranking_metric:
    'Rank by the share of the year’s work completed, the gap from plan, or completed work divided by the work due so far. Offices with equal results share a rank.',
  cutoff_day:
    'If the deadline day is 5, January reports are due by the end of 5 February in the agency’s time zone. Change one month’s deadline on the fiscal year page.',
  auto_lock:
    'Locking a month makes its results final and stops report changes. Lock months in order. An administrator can reopen a month by giving a reason, which is saved in the audit log.',
  mov_required:
    'A supporting file is a photo, scan, or document that shows the work was completed. When files are required, every reported accomplishment needs one before submission.',
  show_actual_amounts:
    'If no spending is entered, estimated funds used equal the budget multiplied by progress to date. Once actual spending is entered, those amounts are shown instead. Complete all entries so the total covers all spending.',
};
