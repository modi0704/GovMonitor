import type { Headline } from '../api/types';
import { money, percent } from '../lib/format';
import NavIcon from '../layout/NavIcon';
import Sparkline from './Sparkline';

function Difference({ value, label }: { value: number; label: string }) {
  const points = Math.round(value * 10000) / 100;
  const tone = points > 0 ? 'positive' : points < 0 ? 'negative' : 'neutral';
  return (
    <span className={`trend-badge trend-${tone}`} title={label}>
      <span aria-hidden="true">{tone === 'positive' ? '↗' : tone === 'negative' ? '↘' : '−'}</span>
      {points > 0 ? '+' : ''}
      {points.toFixed(2)} points
      <span className="sr-only"> {label}</span>
    </span>
  );
}

export function StatusChip({
  result,
}: {
  result: Pick<Headline, 'status'> & { status_kind?: string };
}) {
  // The status word is always shown with its colour (P8.7).
  return <span className={`chip status-${result.status_kind ?? 'on_time'}`}>{result.status}</span>;
}

/** Headline tiles: this month, to date, variance with status, funds (P6.5, P8.2). */
export default function ResultPanel({
  result,
  monthLabel,
  unsaved = false,
  history,
}: {
  result: Headline & { status_kind?: string };
  monthLabel: string;
  unsaved?: boolean;
  history?: { actual: (string | null)[]; planned: string[]; month: number };
}) {
  const number = (v: string | number) => (Number.isFinite(Number(v)) ? Number(v) : 0);
  const monthly = number(result.periodic_actual);
  const monthlyPlan = number(result.periodic_plan);
  const actual = number(result.cum_actual);
  const planned = number(result.cum_plan);
  const total = number(result.funds_total);
  const used = number(result.funds_used_actual ?? result.funds_used_est);
  const budgetShare = total > 0 ? used / total : null;
  const plotActual = history?.actual
    .slice(0, history.month)
    .map((v) => (v === null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v)));
  const plotPlanned = history?.planned.slice(0, history.month).map(Number);
  const prior = plotActual && plotActual.length > 1 ? plotActual[plotActual.length - 2] : null;
  const current = plotActual?.[plotActual.length - 1];
  const gap = plotActual?.map((v, i) =>
    v === null || !Number.isFinite(plotPlanned?.[i]) ? null : v - plotPlanned![i]!,
  );
  const compareScale = Math.max(monthly, monthlyPlan, 0.01);
  const cumulativeScale = Math.max(actual, planned, 0.01);
  return (
    <div className="tiles" aria-live="polite">
      <div className="tile">
        <div className="tile-heading">
          <span className="tile-label">This month</span>
          <NavIcon name="Fiscal years" />
        </div>
        <span className="tile-value">{percent(result.periodic_actual)}</span>
        <div className="tile-comparison">
          <Difference value={monthly - monthlyPlan} label="compared with this month's plan" />
          <span>vs plan</span>
        </div>
        <div className="metric-compare" aria-hidden="true">
          <span style={{ width: `${Math.max(0, monthlyPlan / compareScale) * 100}%` }} />
          <span style={{ width: `${Math.max(0, monthly / compareScale) * 100}%` }} />
        </div>
        <span className="tile-footnote">planned {percent(result.periodic_plan)}</span>
      </div>
      <div className="tile">
        <div className="tile-heading">
          <span className="tile-label">To date</span>
          <NavIcon name="Dashboard" />
        </div>
        <span className="tile-value">{percent(result.cum_actual)}</span>
        <div className="tile-comparison">
          {prior !== null && prior !== undefined && current !== null && current !== undefined ? (
            <>
              <Difference
                value={current - prior}
                label="change in work completed since last month"
              />
              <span>vs last month</span>
            </>
          ) : (
            <span>Work completed so far</span>
          )}
        </div>
        {plotActual ? (
          <Sparkline
            values={plotActual}
            planned={plotPlanned}
            label="Progress to date: actual and planned history"
          />
        ) : (
          <div className="metric-track" aria-hidden="true">
            <span style={{ width: `${Math.min(100, Math.max(0, actual * 100))}%` }} />
          </div>
        )}
        <span className="tile-footnote">planned {percent(result.cum_plan)}</span>
      </div>
      <div className="tile">
        <div className="tile-heading">
          <span className="tile-label">Gap</span>
          <NavIcon name="Rankings" />
        </div>
        <span className="tile-value">{percent(result.variance)}</span>
        <div className="tile-comparison">
          <StatusChip result={result} />
          <span>vs plan to date</span>
        </div>
        {gap ? (
          <Sparkline
            values={gap}
            tone={number(result.variance) < 0 ? 'negative' : 'positive'}
            label="Gap between actual and planned progress over time"
          />
        ) : (
          <div className="metric-compare" aria-hidden="true">
            <span style={{ width: `${Math.max(0, planned / cumulativeScale) * 100}%` }} />
            <span style={{ width: `${Math.max(0, actual / cumulativeScale) * 100}%` }} />
          </div>
        )}
        <span className="tile-footnote">Gap from plan, in percentage points</span>
      </div>
      <div className="tile">
        <div className="tile-heading">
          <span className="tile-label">
            Funds used{result.funds_used_actual === null ? ' (estimate)' : ''}
          </span>
          <NavIcon name="Funds" />
        </div>
        <span className="tile-value small-value">
          {money(result.funds_used_actual ?? result.funds_used_est)}
        </span>
        <div className="tile-comparison">
          <span className="trend-badge trend-neutral">
            {budgetShare === null ? 'No budget' : `${(budgetShare * 100).toFixed(1)}% used`}
          </span>
        </div>
        <div className="metric-track" aria-hidden="true">
          <span style={{ width: `${Math.min(100, Math.max(0, (budgetShare ?? 0) * 100))}%` }} />
        </div>
        <span className="tile-footnote">of {money(result.funds_total)}</span>
      </div>
      <p className="muted small tiles-note">
        {monthLabel}
        {unsaved ? ' · includes numbers not saved yet' : ''}
      </p>
    </div>
  );
}
