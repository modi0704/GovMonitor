/** Longer explanations, with small examples, for every scoring setting (P12.6). */
export const SCORING_TIPS: Record<string, string> = {
  preset:
    'A preset fills in every setting below at once. "Workbook compatible" gives the same numbers as the agency’s Excel monitoring workbook. You can change single settings afterwards; the preset then shows as custom.',
  weighting:
    'Example: activities costing 600,000, 300,000 and 100,000 weigh 60%, 30% and 10% by cost; equal weighting gives each a third; manual weights are typed per activity and must add up to 100%.',
  cap_at_100:
    'Example: plan 10, done 12. Without the ceiling the activity counts 120% and can lift the office above 100%. With it, it counts 100%, so over-delivery cannot hide other activities’ delays.',
  on_time_tolerance:
    'Example with 2 points: plan 50%, done 48.5% → on time; done 47% → behind. Ahead and behind are judged on the cumulative figures for the month.',
  labels:
    'These words appear on dashboards, exports and decks for offices ahead of, on, or behind plan. Changing them does not change any number.',
  rollup:
    'Example: division X (budget 1,000,000, 78%) and Y (budget 3,000,000, 90%). By budget the service scores 87%; as a simple average, 84%.',
  indicator_weighting:
    'Equal: every indicator of an office counts the same. Manual: type a weight per indicator in the plan; weights must add up to 100%.',
  indicator_rollup:
    'All indicators: the parent averages every indicator beneath it. Office scores: the parent averages its offices’ indicator scores, so an office with many indicators does not dominate.',
  ranking_metric:
    'Cumulative accomplishment ranks by the share of the year’s plan done; variance ranks by how far ahead of plan; actual over plan ranks by accomplishment relative to what was due so far. Equal values share a rank.',
  cutoff_day:
    'Example: cutoff day 5 → January reports are due by 5 February, end of day, in the agency’s time zone. Each month’s cutoff can be moved on the fiscal year page.',
  auto_lock:
    'Locked months are final: results are frozen and reports cannot change. Months always lock in order; an administrator can unlock one with a reason (kept in the audit log).',
  mov_required:
    'MOV = means of verification: a photo, scan or document proving the accomplishment. With this on, a report cannot be submitted while an accomplishment has no file.',
  show_actual_amounts:
    'Without amounts, funds used are estimated as budget × cumulative accomplishment and labelled as an estimate. Where amounts are entered, the real figures are shown instead.',
};
