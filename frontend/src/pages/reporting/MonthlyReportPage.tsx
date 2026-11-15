import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApiError, api } from '../../api/client';
import type { FiscalYear, Headline, MonthReport, OfficeRow, ReportActivity } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';
import { dateTime, money, monthYear, percent } from '../../lib/format';
import MovDialog from './MovDialog';
import type { MovTarget } from './movUpload';

interface Edit {
  actual?: string;
  actual_amount?: string;
  remarks?: string;
  delay_reason?: string;
}

interface Problem {
  code: string;
  row: string | null;
  message: string;
}

const SUBMISSION_TEXT = {
  draft: 'Not submitted yet',
  submitted: 'Submitted — waiting for review',
  returned: 'Returned for correction',
  locked: 'Locked — final',
};

export function StatusChip({
  result,
}: {
  result: Pick<Headline, 'status'> & { status_kind?: string };
}) {
  // The status word is always shown with its colour (P8.7).
  return <span className={`chip status-${result.status_kind ?? 'on_time'}`}>{result.status}</span>;
}

function num(v: string | null | undefined): number {
  const n = Number(String(v ?? '').replace(/,/g, ''));
  return Number.isFinite(n) ? n : 0;
}

/** Monthly accomplishment entry (P6.5–P6.8). */
export default function MonthlyReportPage() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const years = useResource<FiscalYear[]>('fiscal-years');
  const offices = useResource<OfficeRow[]>('offices?include_inactive=0');
  const fyId =
    params.get('fy') ??
    years.data?.find((y) => y.status === 'open')?.id ??
    years.data?.[0]?.id ??
    null;
  const fy = useResource<FiscalYear>(fyId ? `fiscal-years/${fyId}` : null);
  const officeId =
    params.get('office') ??
    offices.data?.find((o) => o.can_edit)?.id ??
    offices.data?.[0]?.id ??
    null;
  const view = params.get('view') === 'implementing' ? 'implementing' : 'owner';
  const periods = fy.data?.periods ?? [];
  const periodId =
    params.get('period') ??
    periods.find((p) => p.status === 'open')?.id ??
    periods[periods.length - 1]?.id ??
    null;

  const [report, setReport] = useState<MonthReport | null>(null);
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [indEdits, setIndEdits] = useState<Record<string, Edit>>({});
  const [live, setLive] = useState<(Headline & { status_kind?: string }) | null>(null);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [tab, setTab] = useState<'activities' | 'indicators'>('activities');
  const [mov, setMov] = useState<MovTarget | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const query = useMemo(
    () => (officeId && periodId ? { office: officeId, period: periodId, view } : null),
    [officeId, periodId, view],
  );

  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    if (!query) return;
    let active = true;
    api
      .get<MonthReport>('reports', query)
      .then((data) => {
        if (!active) return;
        setReport(data);
        setLive(data.result);
        setEdits({});
        setIndEdits({});
        setProblems([]);
        setError(null);
      })
      .catch((err: unknown) => active && setError(errorMessage(err)));
    return () => {
      active = false;
    };
  }, [query, reloadKey]);

  const dirty = Object.keys(edits).length > 0 || Object.keys(indEdits).length > 0;

  useEffect(() => {
    if (!dirty) return;
    const guard = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener('beforeunload', guard);
    return () => window.removeEventListener('beforeunload', guard);
  }, [dirty]);

  // Live result panel: ask the engine for the office result with the unsaved numbers (debounced).
  useEffect(() => {
    if (!query || !report || !Object.keys(edits).length) return;
    const activities = report.activities.map((a) => ({
      lineage_id: a.lineage_id,
      actual: edits[a.lineage_id]?.actual ?? a.actual ?? '0',
      actual_amount: edits[a.lineage_id]?.actual_amount ?? a.actual_amount ?? '',
    }));
    const handle = window.setTimeout(() => {
      api
        .post<{ result: Headline | null }>('reports/preview', { ...query, activities })
        .then((r) => setLive(r.result))
        .catch(() => undefined);
    }, 400);
    return () => window.clearTimeout(handle);
  }, [edits, report, query]);

  function choose(next: Record<string, string | null>) {
    const merged: Record<string, string> = {};
    const current = { fy: fyId, office: officeId, period: periodId, view, ...next };
    Object.entries(current).forEach(([k, v]) => {
      if (v) merged[k] = v;
    });
    if (dirty && !window.confirm('You have unsaved changes. Leave them?')) return;
    setParams(merged);
  }

  async function save(): Promise<boolean> {
    if (!query || !report) return false;
    setBusy(true);
    setNotice(null);
    try {
      const data = await api.post<MonthReport>('reports/save', {
        ...query,
        activities: Object.entries(edits).map(([lineage_id, e]) => ({ lineage_id, ...e })),
        indicators: Object.entries(indEdits).map(([lineage_id, e]) => ({ lineage_id, ...e })),
      });
      setReport(data);
      setLive(data.result);
      setEdits({});
      setIndEdits({});
      setError(null);
      setNotice('Saved.');
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!query || !report) return;
    if (
      !window.confirm(
        `Submit the ${report.office.code} report for ${monthYear(report.period.start_date)}? It cannot be changed unless it is returned.`,
      )
    )
      return;
    if (dirty && !(await save())) return;
    setBusy(true);
    try {
      const data = await api.post<MonthReport>('reports/submit', query);
      setReport(data);
      setProblems([]);
      setNotice('Submitted.');
    } catch (err) {
      if (err instanceof ApiError)
        setProblems((err.body as { problems?: Problem[] })?.problems ?? []);
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function returnReport() {
    if (!query) return;
    const note = window.prompt('What needs correcting? The office sees this note.');
    if (!note) return;
    try {
      setReport(await api.post<MonthReport>('reports/return', { ...query, note }));
      setNotice('Returned to the office.');
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const setEdit = (lineage: string, patch: Edit) =>
    setEdits({ ...edits, [lineage]: { ...edits[lineage], ...patch } });
  const problemRows = new Map(problems.filter((p) => p.row).map((p) => [p.row!, p.message]));
  const office = offices.data?.find((o) => o.id === officeId);

  const rowValue = (a: ReportActivity, key: keyof Edit) =>
    edits[a.lineage_id]?.[key] ?? (a[key] as string | null) ?? '';

  return (
    <section className="page page-full">
      <div className="page-header">
        <h1>Monthly report</h1>
      </div>
      <div className="filters">
        <label>
          Office
          <select value={officeId ?? ''} onChange={(e) => choose({ office: e.target.value })}>
            {offices.data?.map((o) => (
              <option key={o.id} value={o.id}>
                {'  '.repeat(o.depth)}
                {o.code} {o.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Show
          <select value={view} onChange={(e) => choose({ view: e.target.value })}>
            <option value="owner">The office's own plan</option>
            <option value="implementing">Activities it carries out for other offices</option>
          </select>
        </label>
        <label>
          Fiscal year
          <select value={fyId ?? ''} onChange={(e) => choose({ fy: e.target.value, period: null })}>
            {years.data?.map((y) => (
              <option key={y.id} value={y.id}>
                {y.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Month
          <select value={periodId ?? ''} onChange={(e) => choose({ period: e.target.value })}>
            {periods.map((p) => (
              <option key={p.id} value={p.id}>
                {monthYear(p.start_date)}
                {p.status === 'locked' ? ' (locked)' : ''}
              </option>
            ))}
          </select>
        </label>
      </div>
      <FormError message={error ?? years.error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {years.data?.length === 0 && <p className="notice">There is no fiscal year yet.</p>}
      {report && !report.has_plan && (
        <p className="notice">
          {view === 'owner'
            ? `${office?.name ?? 'This office'} has no approved plan for ${report.period.fiscal_year.label}. `
            : `${office?.name ?? 'This office'} carries out no activities for other offices this year. `}
          {view === 'owner' && <Link to="/plans">Go to plans</Link>}
        </p>
      )}
      {report && report.has_plan && (
        <>
          <div className="report-head">
            <div>
              <span className={`chip chip-sub-${report.submission.status}`}>
                {SUBMISSION_TEXT[report.submission.status]}
              </span>{' '}
              <span className="muted small">
                Due {dateTime(report.period.cutoff_at)}
                {report.submission.submitted_at &&
                  ` · submitted ${dateTime(report.submission.submitted_at)} by ${report.submission.submitted_by}`}
              </span>
              {report.period.status === 'locked' && (
                <p className="muted small">This month is locked; its figures are final.</p>
              )}
            </div>
            <div className="row">
              {report.activities.some((a) => a.editable) && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={save}
                  disabled={busy || !dirty}
                >
                  {dirty ? 'Save' : 'Saved'}
                </button>
              )}
              {report.can_submit && (
                <button type="button" className="btn" onClick={submit} disabled={busy}>
                  Submit report
                </button>
              )}
              {report.can_return && me?.is_agency_admin && (
                <button type="button" className="btn" onClick={returnReport}>
                  Return for correction
                </button>
              )}
            </div>
          </div>
          {report.submission.status === 'returned' && report.submission.return_note && (
            <p className="form-message">
              <strong>Returned by {report.submission.returned_by}:</strong>{' '}
              {report.submission.return_note}
            </p>
          )}
          {problems.length > 0 && (
            <details className="issues" open>
              <summary>{problems.length} problem(s) stop the report from being submitted</summary>
              <ul>
                {problems.map((p, i) => (
                  <li key={i}>{p.message}</li>
                ))}
              </ul>
            </details>
          )}
          {live && (
            <ResultPanel
              result={live}
              monthLabel={monthYear(report.period.start_date)}
              unsaved={dirty}
            />
          )}
          <div className="tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'activities'}
              onClick={() => setTab('activities')}
            >
              Activities ({report.activities.length})
            </button>
            {view === 'owner' && (
              <button
                type="button"
                role="tab"
                aria-selected={tab === 'indicators'}
                onClick={() => setTab('indicators')}
              >
                Indicators ({report.indicators.length})
              </button>
            )}
          </div>
          {tab === 'activities' ? (
            <div className="grid-scroll">
              <table className="grid report-grid" aria-label="Activities this month">
                <thead>
                  <tr>
                    <th>Activity</th>
                    {view === 'implementing' ? <th>For office</th> : <th>Carried out by</th>}
                    <th>Target this month</th>
                    <th>Done this month</th>
                    {report.show_amounts && <th>Amount spent</th>}
                    <th>To date: target / done</th>
                    <th>Progress</th>
                    <th>Reason for delay</th>
                    <th>Remarks</th>
                    <th>Files</th>
                  </tr>
                </thead>
                <tbody>
                  {report.activities.map((a) => {
                    const done = num(a.prev_cum_actual) + num(rowValue(a, 'actual'));
                    const problem = problemRows.get(a.lineage_id);
                    return (
                      <tr key={a.lineage_id} className={`act ${problem ? 'has-error' : ''}`}>
                        <td className="title-cell">
                          <span className="code">{a.code}</span> {a.title}
                          <div className="muted small">
                            {a.unit} · year target {a.annual_target}
                          </div>
                          {problem && <div className="text-delayed small">{problem}</div>}
                        </td>
                        <td>
                          {view === 'implementing'
                            ? a.owner_office.code
                            : a.implementing_office.code}
                        </td>
                        <td className="num pad">{a.target_month}</td>
                        <td className="num">
                          <input
                            aria-label={`Done this month, ${a.code || a.title}`}
                            inputMode="decimal"
                            value={rowValue(a, 'actual')}
                            readOnly={!a.editable}
                            onChange={(e) => setEdit(a.lineage_id, { actual: e.target.value })}
                          />
                        </td>
                        {report.show_amounts && (
                          <td className="num">
                            <input
                              aria-label={`Amount spent, ${a.code || a.title}`}
                              inputMode="decimal"
                              value={rowValue(a, 'actual_amount')}
                              readOnly={!a.editable}
                              onChange={(e) =>
                                setEdit(a.lineage_id, { actual_amount: e.target.value })
                              }
                            />
                          </td>
                        )}
                        <td className="num pad">
                          {a.cum_target} / {Number.isInteger(done) ? done : done.toFixed(2)}
                        </td>
                        <td className="pad">
                          <Progress
                            planned={Number(a.planned_ratio)}
                            actual={Number(a.actual_ratio)}
                          />
                          {!a.no_target && (
                            <span
                              className={`chip ${a.behind ? 'status-delayed' : 'status-on_time'}`}
                            >
                              {a.behind ? 'Behind' : 'On track'}
                            </span>
                          )}
                        </td>
                        <td>
                          {(a.behind || a.delay_reason) && (
                            <input
                              aria-label={`Reason for delay, ${a.code || a.title}`}
                              placeholder={a.behind ? 'Required' : ''}
                              value={rowValue(a, 'delay_reason')}
                              readOnly={!a.editable}
                              onChange={(e) =>
                                setEdit(a.lineage_id, { delay_reason: e.target.value })
                              }
                            />
                          )}
                        </td>
                        <td>
                          <input
                            aria-label={`Remarks, ${a.code || a.title}`}
                            value={rowValue(a, 'remarks')}
                            readOnly={!a.editable}
                            onChange={(e) => setEdit(a.lineage_id, { remarks: e.target.value })}
                          />
                        </td>
                        <td className="pad">
                          <button
                            type="button"
                            className="btn btn-small"
                            onClick={() =>
                              setMov({
                                targetType: 'activity_actual',
                                lineageId: a.lineage_id,
                                periodId: report.period.id,
                                label: a.code || a.title,
                                editable: a.editable,
                              })
                            }
                          >
                            {a.attachments
                              ? `${a.attachments} file${a.attachments > 1 ? 's' : ''}`
                              : a.editable
                                ? 'Attach'
                                : 'None'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid-scroll">
              <table className="grid report-grid" aria-label="Indicators this month">
                <thead>
                  <tr>
                    <th>Indicator</th>
                    <th>Year target</th>
                    <th>Target this month</th>
                    <th>{'Value this month'}</th>
                    <th>Remarks</th>
                    <th>Files</th>
                  </tr>
                </thead>
                <tbody>
                  {report.indicators.length === 0 && (
                    <tr>
                      <td colSpan={6} className="pad muted">
                        This plan has no indicators.
                      </td>
                    </tr>
                  )}
                  {report.indicators.map((i) => {
                    const editable = report.activities.some((a) => a.editable) || report.can_submit;
                    return (
                      <tr key={i.lineage_id} className="act">
                        <td className="title-cell pad">
                          <span className="code">{i.code}</span> {i.name}
                          <div className="muted small">
                            {i.aggregation === 'last' ? 'Latest value counts' : 'Months add up'}
                          </div>
                        </td>
                        <td className="num pad">{i.annual_target}</td>
                        <td className="num pad">{i.target_month}</td>
                        <td className="num">
                          <input
                            aria-label={`Value this month, ${i.code || i.name}`}
                            inputMode="decimal"
                            value={indEdits[i.lineage_id]?.actual ?? i.actual ?? ''}
                            readOnly={!editable}
                            onChange={(e) =>
                              setIndEdits({
                                ...indEdits,
                                [i.lineage_id]: {
                                  ...indEdits[i.lineage_id],
                                  actual: e.target.value,
                                },
                              })
                            }
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Remarks, ${i.code || i.name}`}
                            value={indEdits[i.lineage_id]?.remarks ?? i.remarks}
                            readOnly={!editable}
                            onChange={(e) =>
                              setIndEdits({
                                ...indEdits,
                                [i.lineage_id]: {
                                  ...indEdits[i.lineage_id],
                                  remarks: e.target.value,
                                },
                              })
                            }
                          />
                        </td>
                        <td className="pad">
                          <button
                            type="button"
                            className="btn btn-small"
                            onClick={() =>
                              setMov({
                                targetType: 'indicator_actual',
                                lineageId: i.lineage_id,
                                periodId: report.period.id,
                                label: i.code || i.name,
                                editable,
                              })
                            }
                          >
                            {i.attachments
                              ? `${i.attachments} file(s)`
                              : editable
                                ? 'Attach'
                                : 'None'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      {mov && <MovDialog target={mov} onClose={() => setMov(null)} onChanged={load} />}
    </section>
  );
}

function Progress({ planned, actual }: { planned: number; actual: number }) {
  const width = (v: number) => `${Math.min(100, Math.max(0, v * 100))}%`;
  return (
    <div
      className="progress"
      title={`Done ${percent(actual)} of the year target; planned by now ${percent(planned)}`}
    >
      <div className="progress-actual" style={{ width: width(actual) }} />
      <div className="progress-plan" style={{ left: width(planned) }} />
    </div>
  );
}

export function ResultPanel({
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
