import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import type { FiscalYear, OfficeRow } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import { api } from '../../api/client';
import Chart from '../../components/Chart';
import { CHART_COLORS } from '../../components/chartTheme';
import FormError from '../../components/FormError';
import ResultPanel, { StatusChip } from '../../components/ResultTiles';
import { money, monthName, monthYear, percent } from '../../lib/format';
import ActivitiesPanel from './ActivitiesPanel';
import type { Dashboard, RankingSet } from './types';

const ExportDialog = lazy(() => import('../exports/ExportDialog'));

/** Default month: the latest locked month, otherwise the first open one. */
function defaultPeriod(fy: FiscalYear | null): string | null {
  const periods = fy?.periods ?? [];
  const locked = periods.filter((p) => p.status === 'locked');
  return (
    (locked[locked.length - 1] ?? periods.find((p) => p.status === 'open') ?? periods[0])?.id ??
    null
  );
}

/** Agency and office dashboards with drill-down (P8.2, P8.3, P8.5). */
export default function DashboardPage() {
  const [params, setParams] = useSearchParams();
  const years = useResource<FiscalYear[]>('fiscal-years');
  const offices = useResource<OfficeRow[]>('offices');
  const fyId =
    params.get('fy') ??
    years.data?.find((y) => y.status === 'open')?.id ??
    years.data?.[0]?.id ??
    null;
  const fy = useResource<FiscalYear>(fyId ? `fiscal-years/${fyId}` : null);
  const topOffice = useMemo(() => {
    const ids = new Set((offices.data ?? []).map((o) => o.id));
    return offices.data?.find((o) => !o.parent_id || !ids.has(o.parent_id))?.id ?? null;
  }, [offices.data]);
  const officeId = params.get('office') ?? topOffice;
  const periodId = params.get('period') ?? defaultPeriod(fy.data);
  const view = params.get('view') === 'implementing' ? 'implementing' : 'owner';
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'overview' | 'activities'>('overview');
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!officeId || !periodId) return;
    let active = true;
    api
      .get<Dashboard>('dashboard', { office: officeId, period: periodId, view })
      .then((d) => {
        if (!active) return;
        setData(d);
        setError(null);
      })
      .catch((err: unknown) => active && setError(errorMessage(err)));
    return () => {
      active = false;
    };
  }, [officeId, periodId, view]);

  function go(next: Record<string, string | null>) {
    const merged: Record<string, string> = {};
    const current: Record<string, string | null> = {
      fy: fyId,
      office: officeId,
      period: periodId,
      view,
      ...next,
    };
    Object.entries(current).forEach(([k, v]) => {
      if (v && !(k === 'view' && v === 'owner')) merged[k] = v;
    });
    setParams(merged);
  }

  const months = (data?.months ?? []).map((m) => monthName(m, true));
  const h = data?.headline;

  return (
    <section className="page page-wide">
      <div className="page-header">
        <div>
          {data && (
            <p className="breadcrumb" aria-label="Office path">
              {data.office.ancestors.map((a) => (
                <span key={a.id}>
                  <button
                    type="button"
                    className="btn-link-plain"
                    onClick={() => go({ office: a.id, view: null })}
                  >
                    {a.code}
                  </button>{' '}
                  ›{' '}
                </span>
              ))}
              <strong>{data.office.code}</strong>
            </p>
          )}
          <h1>{data ? data.office.name : 'Dashboard'}</h1>
        </div>
        {data && (
          <div className="row">
            <span className={`badge ${data.final ? 'badge-final' : 'badge-provisional'}`}>
              {data.label}
            </span>
            <button type="button" className="btn" onClick={() => setExporting(true)}>
              Export
            </button>
          </div>
        )}
      </div>
      {exporting && data && (
        <Suspense fallback={null}>
          <ExportDialog
            officeId={data.office.id}
            officeLabel={`${data.office.code} ${data.office.name}`}
            periods={fy.data?.periods ?? []}
            periodId={data.period.id}
            view={view}
            canExportAgency={(offices.data ?? []).some((o) => o.depth === 0)}
            onClose={() => setExporting(false)}
          />
        </Suspense>
      )}
      <div className="filters">
        <label>
          Fiscal year
          <select value={fyId ?? ''} onChange={(e) => go({ fy: e.target.value, period: null })}>
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
            {fy.data?.periods?.map((p) => (
              <option key={p.id} value={p.id}>
                {monthYear(p.start_date)}
                {p.status === 'locked' ? ' (final)' : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          Office
          <select
            value={officeId ?? ''}
            onChange={(e) => go({ office: e.target.value, view: null })}
          >
            {offices.data?.map((o) => (
              <option key={o.id} value={o.id}>
                {'  '.repeat(o.depth)}
                {o.code} {o.name}
              </option>
            ))}
          </select>
        </label>
        {data && data.views.length > 1 && (
          <label>
            Scores of
            <select value={view} onChange={(e) => go({ view: e.target.value })}>
              <option value="owner">Its own plan (with offices beneath)</option>
              <option value="implementing">Activities it carries out</option>
            </select>
          </label>
        )}
      </div>
      <FormError message={error ?? years.error} />
      {years.data?.length === 0 && <p className="notice">There is no fiscal year yet.</p>}
      {data && !data.has_result && (
        <p className="notice">
          {data.office.name} has no results for {monthYear(data.period.start_date)}: no approved
          plan covers it yet. {data.children.length > 0 && 'Choose one of its offices below.'}
        </p>
      )}
      {data && h && data.series && (
        <>
          <ResultPanel
            result={h}
            monthLabel={`${monthYear(data.period.start_date)} · ${data.label === 'FINAL' ? 'final figures' : 'provisional, the month is still open'}`}
          />
          <div className="tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'overview'}
              onClick={() => setTab('overview')}
            >
              Overview
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'activities'}
              onClick={() => setTab('activities')}
            >
              Activities
            </button>
          </div>
        </>
      )}
      {data && h && data.series && tab === 'activities' && (
        <ActivitiesPanel officeId={data.office.id} periodId={data.period.id} view={view} />
      )}
      {data && h && data.series && tab === 'overview' && (
        <div className="dash-grid">
          <Chart
            label="Progress to date: plan and actual (cumulative)"
            height={260}
            option={{
              grid: { left: 45, right: 15, top: 30, bottom: 30 },
              legend: { top: 0 },
              tooltip: {
                trigger: 'axis',
                valueFormatter: (v: number | null) => (v === null ? '—' : percent(v)),
              },
              xAxis: { type: 'category', data: months },
              yAxis: {
                type: 'value',
                axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` },
              },
              series: [
                {
                  type: 'line',
                  name: 'Plan',
                  data: data.series.cum_plan.map(Number),
                  color: CHART_COLORS.plan,
                  lineStyle: { type: 'dashed' },
                },
                {
                  type: 'line',
                  name: 'Actual',
                  data: data.series.cum_actual.map((v) => (v === null ? null : Number(v))),
                  color: CHART_COLORS.actual,
                  symbolSize: 7,
                },
              ],
            }}
            table={{
              caption: 'Cumulative plan and actual by month',
              headers: ['Month', 'Plan', 'Actual'],
              rows: months.map((m, i) => [
                m,
                percent(data.series!.cum_plan[i] ?? null),
                percent(data.series!.cum_actual[i] ?? null),
              ]),
            }}
          />
          <FundsChart
            total={h.funds_total}
            used={h.funds_used_actual ?? h.funds_used_est}
            estimate={h.funds_used_actual === null}
          />
          {data.quarters.length > 0 && (
            <div className="card dash-wide">
              <h2>By quarter</h2>
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Period</th>
                    <th>Plan</th>
                    <th>Actual</th>
                    <th>Variance</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.quarters.map((q) => (
                    <tr key={q.quarter}>
                      <td>
                        Q{q.quarter} ({months[q.first - 1]}–{months[q.last - 1]})
                        {q.partial ? ', so far' : ''}
                      </td>
                      <td>{percent(q.plan)}</td>
                      <td>{percent(q.actual)}</td>
                      <td>{percent(q.variance)}</td>
                      <td>
                        <StatusChip result={q} />
                      </td>
                    </tr>
                  ))}
                  <tr>
                    <td>
                      <strong>Year to date</strong>
                    </td>
                    <td>{percent(h.cum_plan)}</td>
                    <td>
                      <strong>{percent(h.cum_actual)}</strong>
                    </td>
                    <td>{percent(h.variance)}</td>
                    <td>
                      <StatusChip result={h} />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
          {data.children.length > 0 && (
            <div className="card dash-wide">
              <h2>Offices under {data.office.code}</h2>
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Office</th>
                    <th>Plan to date</th>
                    <th>Actual to date</th>
                    <th>Variance</th>
                    <th>Status</th>
                    <th>Rank</th>
                    <th>Funds</th>
                  </tr>
                </thead>
                <tbody>
                  {data.children.map((c) => (
                    <tr key={c.office.id}>
                      <td>
                        <button
                          type="button"
                          className="btn-link-plain"
                          onClick={() => go({ office: c.office.id, view: null })}
                        >
                          <span className="code">{c.office.code}</span> {c.office.name}
                        </button>
                      </td>
                      {c.result ? (
                        <>
                          <td>{percent(c.result.cum_plan)}</td>
                          <td>
                            <strong>{percent(c.result.cum_actual)}</strong>
                          </td>
                          <td>{percent(c.result.variance)}</td>
                          <td>
                            <StatusChip result={c.result} />
                          </td>
                          <td>{c.result.rank_sibling ?? '—'}</td>
                          <td>{money(c.result.funds_total)}</td>
                        </>
                      ) : (
                        <td colSpan={6} className="muted">
                          No approved plan
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {data.rankings.map((r) => (
            <RankingCard
              key={`${r.set.kind}-${r.set.id}`}
              ranking={r}
              onOpen={(id) => go({ office: id, view: null })}
            />
          ))}
          {data.indicators.length > 0 && (
            <div className="card dash-wide">
              <h2>Indicators</h2>
              <table className="table compact">
                <thead>
                  <tr>
                    <th>Indicator</th>
                    <th>Annual target</th>
                    <th>Actual to date</th>
                    <th>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {data.indicators.map((i) => (
                    <tr key={i.lineage_id}>
                      <td>
                        <span className="code">{i.code}</span> {i.name}
                      </td>
                      <td>{i.annual_target}</td>
                      <td>{i.actual_to_date ?? '—'}</td>
                      <td>{percent(i.rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {h.indicator_score !== null && (
                <p className="muted small">Indicator score: {percent(h.indicator_score)}</p>
              )}
            </div>
          )}
        </div>
      )}
      {data && !h && data.children.length > 0 && (
        <ul className="plain-list">
          {data.children.map((c) => (
            <li key={c.office.id}>
              <button
                type="button"
                className="btn-link-plain"
                onClick={() => go({ office: c.office.id })}
              >
                <span className="code">{c.office.code}</span> {c.office.name}
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="muted small">
        <Link to="/rankings">All rankings</Link>
      </p>
    </section>
  );
}

function FundsChart({ total, used, estimate }: { total: string; used: string; estimate: boolean }) {
  const remaining = Math.max(0, Number(total) - Number(used));
  return (
    <Chart
      label={`Funds used${estimate ? ' (estimate)' : ''} and remaining`}
      height={260}
      option={{
        tooltip: { trigger: 'item', valueFormatter: (v: number) => money(v) },
        legend: { bottom: 0 },
        series: [
          {
            type: 'pie',
            radius: ['50%', '75%'],
            label: { show: false },
            data: [
              {
                name: estimate ? 'Used (estimate)' : 'Used',
                value: Number(used),
                itemStyle: { color: CHART_COLORS.actual },
              },
              { name: 'Remaining', value: remaining, itemStyle: { color: CHART_COLORS.remaining } },
            ],
          },
        ],
      }}
      table={{
        caption: 'Funds',
        headers: ['', 'Amount'],
        rows: [
          ['Total', money(total)],
          [estimate ? 'Used (estimate)' : 'Used', money(used)],
          ['Remaining', money(remaining)],
        ],
      }}
    />
  );
}

export function RankingCard({
  ranking,
  onOpen,
}: {
  ranking: RankingSet;
  onOpen?: (officeId: string) => void;
}) {
  return (
    <div className="card">
      <h2>Ranking · {ranking.set.name}</h2>
      <table className="table compact">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Office</th>
            <th>Actual to date</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {ranking.rows.map((r) => (
            <tr key={r.office.id}>
              <td>{r.rank ?? '—'}</td>
              <td>
                {onOpen ? (
                  <button
                    type="button"
                    className="btn-link-plain"
                    onClick={() => onOpen(r.office.id)}
                  >
                    <span className="code">{r.office.code}</span> {r.office.name}
                  </button>
                ) : (
                  <>
                    <span className="code">{r.office.code}</span> {r.office.name}
                  </>
                )}
              </td>
              <td>{r.result ? percent(r.result.cum_actual) : 'No result'}</td>
              <td>{r.result && <StatusChip result={r.result} />}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
