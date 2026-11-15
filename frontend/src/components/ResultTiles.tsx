import type { Headline } from '../api/types';
import { money, percent } from '../lib/format';

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
}: {
  result: Headline & { status_kind?: string };
  monthLabel: string;
  unsaved?: boolean;
}) {
  return (
    <div className="tiles" aria-live="polite">
      <div className="tile">
        <span className="tile-label">This month</span>
        <span className="tile-value">{percent(result.periodic_actual)}</span>
        <span className="muted small">planned {percent(result.periodic_plan)}</span>
      </div>
      <div className="tile">
        <span className="tile-label">To date</span>
        <span className="tile-value">{percent(result.cum_actual)}</span>
        <span className="muted small">planned {percent(result.cum_plan)}</span>
      </div>
      <div className="tile">
        <span className="tile-label">Variance</span>
        <span className="tile-value">{percent(result.variance)}</span>
        <StatusChip result={result} />
      </div>
      <div className="tile">
        <span className="tile-label">
          Funds used{result.funds_used_actual === null ? ' (estimate)' : ''}
        </span>
        <span className="tile-value small-value">
          {money(result.funds_used_actual ?? result.funds_used_est)}
        </span>
        <span className="muted small">of {money(result.funds_total)}</span>
      </div>
      <p className="muted small tiles-note">
        {monthLabel}
        {unsaved ? ' · includes numbers not saved yet' : ''}
      </p>
    </div>
  );
}
