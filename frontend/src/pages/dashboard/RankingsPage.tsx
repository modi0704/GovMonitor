import { Link, useSearchParams } from 'react-router-dom';
import type { FiscalYear } from '../../api/types';
import { useResource } from '../../api/useResource';
import Chart from '../../components/Chart';
import { CHART_COLORS } from '../../components/chartTheme';
import FormError from '../../components/FormError';
import { StatusChip } from '../../components/ResultTiles';
import { monthYear, percent } from '../../lib/format';
import type { OfficeRef, ResultSummary } from './types';

interface Rankings {
  sets: { key: string; kind: 'children' | 'group'; name: string }[];
  set: { key: string; name: string } | null;
  metric: string;
  label: string;
  previous_month: string | null;
  rows: {
    office: OfficeRef;
    rank: number | null;
    value: string | null;
    result: ResultSummary | null;
    previous_rank: number | null;
    change: number | null;
  }[];
}

const METRIC = {
  cumulative_actual: 'Work completed to date',
  variance: 'Gap from plan',
  actual_over_plan: 'Completed work compared with work due',
} as Record<string, string>;

function Change({ change }: { change: number | null }) {
  if (change === null) return <span className="muted">—</span>;
  if (change === 0) return <span className="muted">no change</span>;
  return change > 0 ? (
    <span className="text-ahead">▲ {change}</span>
  ) : (
    <span className="text-delayed">▼ {-change}</span>
  );
}

/** Rankings (P8.4): offices under the same office; change against last month. */
export default function RankingsPage() {
  const [params, setParams] = useSearchParams();
  const years = useResource<FiscalYear[]>('fiscal-years');
  const fyId =
    params.get('fy') ??
    years.data?.find((y) => y.status === 'open')?.id ??
    years.data?.[0]?.id ??
    null;
  const fy = useResource<FiscalYear>(fyId ? `fiscal-years/${fyId}` : null);
  const periods = fy.data?.periods ?? [];
  const locked = periods.filter((p) => p.status === 'locked');
  const periodId = params.get('period') ?? (locked[locked.length - 1] ?? periods[0])?.id ?? null;
  const setKey = params.get('set') ?? '';
  const data = useResource<Rankings>(
    periodId
      ? `rankings?period=${periodId}${setKey ? `&set=${encodeURIComponent(setKey)}` : ''}`
      : null,
  );
  const d = data.data;
  const ranked = d?.rows.filter((r) => r.value !== null) ?? [];

  function go(next: Record<string, string>) {
    setParams({
      ...(fyId ? { fy: fyId } : {}),
      ...(periodId ? { period: periodId } : {}),
      ...(setKey ? { set: setKey } : {}),
      ...next,
    });
  }

  return (
    <section className="page page-wide">
      <div className="page-header">
        <h1>Rankings</h1>
        {d && (
          <span className={`badge ${d.label === 'FINAL' ? 'badge-final' : 'badge-provisional'}`}>
            {d.label === 'FINAL' ? 'FINAL' : 'NOT FINAL'}
          </span>
        )}
      </div>
      <div className="filters">
        <label>
          Year
          <select value={fyId ?? ''} onChange={(e) => setParams({ fy: e.target.value })}>
            {years.data?.map((y) => (
              <option key={y.id} value={y.id}>
                {y.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Month
          <select value={periodId ?? ''} onChange={(e) => go({ period: e.target.value })}>
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {monthYear(p.start_date)}
                {p.status === 'locked' ? ' (final)' : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ranking
          <select value={d?.set?.key ?? setKey} onChange={(e) => go({ set: e.target.value })}>
            {d?.sets.map((s) => (
              <option key={s.key} value={s.key}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <FormError message={data.error} />
      {d && d.sets.length === 0 && (
        <p className="notice">
          There are no offices to compare yet. Rankings need at least two offices under the same
          office.
        </p>
      )}
      {d && d.set && (
        <>
          <p className="muted">
            Ranked by {(METRIC[d.metric] ?? d.metric).toLowerCase()}. Equal values share a rank.
            Offices without a result are listed last.
            {d.previous_month && ` Change is against ${monthYear(d.previous_month)}.`}
          </p>
          <div className="dash-grid">
            <div className="card">
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Office</th>
                    <th>{METRIC[d.metric] ?? 'Value'}</th>
                    <th>Status</th>
                    <th>Change</th>
                  </tr>
                </thead>
                <tbody>
                  {d.rows.map((r) => (
                    <tr key={r.office.id}>
                      <td>
                        <strong>{r.rank ?? '—'}</strong>
                      </td>
                      <td>
                        <Link to={`/dashboard?office=${r.office.id}&period=${periodId}`}>
                          <span className="code">{r.office.code}</span> {r.office.name}
                        </Link>
                      </td>
                      <td>{r.value === null ? 'No result' : percent(r.value)}</td>
                      <td>{r.result && <StatusChip result={r.result} />}</td>
                      <td>
                        <Change change={r.change} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Chart
              label={d.set.name}
              height={Math.max(180, ranked.length * 34 + 40)}
              option={{
                grid: { left: 90, right: 40, top: 10, bottom: 25 },
                xAxis: {
                  type: 'value',
                  axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` },
                },
                yAxis: { type: 'category', inverse: true, data: ranked.map((r) => r.office.code) },
                tooltip: { valueFormatter: (v: number) => percent(v) },
                series: [
                  {
                    type: 'bar',
                    data: ranked.map((r) => Number(r.value)),
                    color: CHART_COLORS.actual,
                    label: {
                      show: true,
                      position: 'right',
                      formatter: (p: { value: number }) => percent(p.value),
                    },
                  },
                ],
              }}
              table={{
                caption: d.set.name,
                headers: ['Rank', 'Office', 'Value'],
                rows: ranked.map((r) => [r.rank ?? '—', r.office.code, percent(r.value)]),
              }}
            />
          </div>
        </>
      )}
    </section>
  );
}
