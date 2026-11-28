import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApiError, api } from '../../api/client';
import type { FiscalYear, Headline, MonthReport, OfficeRow, ReportActivity } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { dateTime, monthYear, percent } from '../../lib/format';
import ResultPanel from '../../components/ResultTiles';
import MovDialog from './MovDialog';
import type { MovTarget } from './movUpload';
import { ACTIVITY_STATUS_WORD } from '../../lib/statusWords';
import { useUnsavedChanges } from '../../lib/unsaved';

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

// D49: one officer enters everything, so a month is either still being entered or done.
const SUBMISSION_TEXT = {
  draft: 'Not done yet',
  submitted: 'Done',
  returned: 'Not done yet',
  locked: 'Closed — final',
};

function num(v: string | null | undefined): number {
  const n = Number(String(v ?? '').replace(/,/g, ''));
  return Number.isFinite(n) ? n : 0;
}

/** Monthly accomplishment entry (P6.5–P6.8). */
export default function MonthlyReportPage() {
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
    () => (officeId && periodId ? { office: officeId, period: periodId } : null),
    [officeId, periodId],
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

  useUnsavedChanges('monthly-report', dirty);

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
    const current = { fy: fyId, office: officeId, period: periodId, ...next };
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
        `Mark the ${report.office.code} results for ${monthYear(report.period.start_date)} as done? You can still change them until the month is closed.`,
      )
    )
      return;
    if (dirty && !(await save())) return;
    setBusy(true);
    try {
      const data = await api.post<MonthReport>('reports/submit', query);
      setReport(data);
      setProblems([]);
      setNotice('Marked as done.');
    } catch (err) {
      if (err instanceof ApiError)
        setProblems((err.body as { problems?: Problem[] })?.problems ?? []);
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function reopen() {
    if (!query) return;
    setBusy(true);
    try {
      setReport(await api.post<MonthReport>('reports/reopen', query));
      setNotice('You can change the results again.');
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
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
        <h1>Monthly results</h1>
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
          Year
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
                {p.status === 'locked' ? ' (closed)' : ''}
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
      {years.data?.length === 0 && (
        <p className="notice">
          There is no year yet. Add one on the Years page; then each office&apos;s final plan
          appears here for the monthly results.
        </p>
      )}
      {report && !report.has_plan && (
        <p className="notice">
          {`${office?.name ?? 'This office'} has no final plan for ${report.period.fiscal_year.label}. `}
          <Link to="/plans">Go to plans</Link>
        </p>
      )}
      {report && report.has_plan && (
        <>
          <div className="report-head">
            <div>
              <span className={`chip chip-sub-${report.submission.status}`}>
                {SUBMISSION_TEXT[report.submission.status]}
              </span>{' '}
              {report.submission.status === 'submitted' && report.submission.submitted_at && (
                <span className="muted small">
                  Marked as done {dateTime(report.submission.submitted_at)}
                </span>
              )}
              {report.period.status === 'locked' && (
                <p className="muted small">This month is closed; its figures are final.</p>
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
                  Mark as done
                </button>
              )}
              {report.submission.status === 'submitted' && report.period.status === 'open' && (
                <button type="button" className="btn" onClick={reopen} disabled={busy}>
                  Change results
                </button>
              )}
            </div>
          </div>
          {problems.length > 0 && (
            <details className="issues" open>
              <summary>
                {problems.length} problem(s) stop the month from being marked as done
              </summary>
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
            <button
              type="button"
              role="tab"
              aria-selected={tab === 'indicators'}
              onClick={() => setTab('indicators')}
            >
              Indicators ({report.indicators.length})
            </button>
          </div>
          {tab === 'activities' ? (
            <div className="grid-scroll">
              <table className="grid report-grid" aria-label="Activities this month">
                <thead>
                  <tr>
                    <th>Activity</th>
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
                              {ACTIVITY_STATUS_WORD[a.behind ? 'delayed' : 'on_time']}
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
