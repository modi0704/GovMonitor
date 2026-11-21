import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { Period } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import { useAuth } from '../../auth/useAuth';
import FormError from '../../components/FormError';
import StepProgress from '../../components/StepProgress';
import { monthYear } from '../../lib/format';
import { MONTH_WORD, PLAN_WORD, STEPS, stepIndex, type StepKey } from '../../lib/steps';
import ExportDialog from '../exports/ExportDialog';

interface OfficeRef {
  id: string;
  code: string;
  name: string;
  depth: number;
}

export interface Progress {
  steps: { key: StepKey; done: boolean; started?: boolean }[];
  current: StepKey;
  offices_count: number;
  root: OfficeRef | null;
  fiscal_years: { id: string; label: string; status: string }[];
  fiscal_year: { id: string; label: string; status: string } | null;
  plans: {
    office: OfficeRef;
    plan_id: string | null;
    status: 'none' | 'draft' | 'submitted' | 'approved';
    activities: number;
    indicators: number;
    budget: string | null;
  }[];
  period: { id: string; month_index: number; start_date: string; status: string } | null;
  months: {
    id: string;
    month_index: number;
    start_date: string;
    status: string;
    offices_done: number;
    offices_total: number;
  }[];
  monthly: { office: OfficeRef; status: string }[];
}

const isStep = (v: string | null): v is StepKey => STEPS.some((s) => s.key === v);

/** Step-by-step: the monitoring routine with a progress bar (the administrator's start page). */
export default function GuidedStepsPage() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const query = new URLSearchParams();
  if (params.get('fy')) query.set('fiscal_year', params.get('fy')!);
  if (params.get('period')) query.set('period', params.get('period')!);
  const path = `progress${query.size ? `?${query}` : ''}`;
  const progress = useResource<Progress>(path);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState<'monthly' | 'year' | null>(null);

  const p = progress.data;
  const active: StepKey = isStep(params.get('step'))
    ? (params.get('step') as StepKey)
    : (p?.current ?? 'offices');
  const index = stepIndex(active);
  const step = STEPS[index] ?? STEPS[0]!;
  const prev = STEPS[index - 1];
  const next = STEPS[index + 1];

  function go(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params);
    Object.entries(next).forEach(([k, v]) => (v ? merged.set(k, v) : merged.delete(k)));
    setParams(merged);
    setNotice(null);
    setError(null);
  }

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setNotice(done);
      progress.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function startPlan(officeId: string) {
    if (!p?.fiscal_year) return;
    setBusy(true);
    try {
      const plan = await api.post<{ id: string }>('plans', {
        office_id: officeId,
        fiscal_year_id: p.fiscal_year.id,
      });
      navigate(`/plans/${plan.id}`);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  function finishPlan(planId: string, status: string, office: string) {
    if (
      !window.confirm(
        `Mark the plan of ${office} as final? Its figures will be used for the monthly results. You can still revise it later.`,
      )
    )
      return;
    void run(async () => {
      if (status === 'draft') await api.post(`plans/${planId}/submit`);
      await api.post(`plans/${planId}/approve`);
    }, `The plan of ${office} is final.`);
  }

  function closeMonth() {
    if (!p?.period) return;
    const month = monthYear(p.period.start_date);
    const missing = p.monthly.filter((r) => !['submitted', 'locked'].includes(r.status)).length;
    const warning = missing
      ? ` ${missing} office(s) are not marked as done yet; their current figures will be used.`
      : '';
    if (
      !window.confirm(
        `Close ${month}? Its figures become final and can no longer be changed.${warning}`,
      )
    )
      return;
    void run(
      () => api.post(`periods/${p.period!.id}/lock`),
      `${month} is closed. Its figures are final.`,
    );
  }

  const setupNotice = me && !me.agency.setup_complete && (
    <div className="page notice">
      <strong>Your agency is not set up yet.</strong>
      Answer a few questions and the app builds your list of offices.
      <Link to="/setup">Start the setup</Link>
    </div>
  );
  if (!p)
    return (
      <section className="page guided-steps">
        {setupNotice}
        {progress.loading ? (
          <div className="page-loading">Loading…</div>
        ) : (
          <FormError message={progress.error} />
        )}
      </section>
    );

  const fyId = p.fiscal_year?.id;
  const periodId = p.period?.id;
  const month = p.period ? monthYear(p.period.start_date) : '';
  const periods: Period[] = p.months.map((m) => ({
    id: m.id,
    month_index: m.month_index,
    start_date: m.start_date,
    end_date: m.start_date,
    cutoff_at: m.start_date,
    status: m.status as Period['status'],
    locked_at: null,
  }));

  return (
    <section className="page guided-steps">
      {setupNotice}
      <header className="page-header">
        <div>
          <h1>Step-by-step</h1>
          <p className="muted">
            Follow the steps in order. Collect the figures from your offices first, then enter them
            here. The progress bar shows how far you are.
          </p>
        </div>
        <div className="row">
          {p.fiscal_years.length > 0 && (
            <label>
              Year
              <select value={fyId ?? ''} onChange={(e) => go({ fy: e.target.value, period: null })}>
                {p.fiscal_years.map((y) => (
                  <option key={y.id} value={y.id}>
                    {y.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {p.months.length > 0 && (
            <label>
              Month
              <select value={periodId ?? ''} onChange={(e) => go({ period: e.target.value })}>
                {p.months.map((m) => (
                  <option key={m.id} value={m.id}>
                    {monthYear(m.start_date)}
                    {m.status === 'locked' ? ' (closed)' : ''}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </header>

      <StepProgress
        states={p.steps}
        active={active}
        linkTo={(key) => {
          const q = new URLSearchParams(params);
          q.set('step', key);
          return `/?${q}`;
        }}
      />

      <div className="step-card" aria-live="polite">
        <h2>
          <span className="step-badge">Step {index + 1}</span> {step.title}
        </h2>
        <p>{step.why}</p>
        {step.gather.length > 0 && (
          <div className="step-gather">
            <h3>Before you start, collect from the offices</h3>
            <ul>
              {step.gather.map((g) => (
                <li key={g}>{g}</li>
              ))}
            </ul>
          </div>
        )}
        {notice && <p className="notice">{notice}</p>}
        <FormError message={error} />

        {active === 'offices' && (
          <div className="stack">
            <p>
              {p.offices_count > 0
                ? `You have ${p.offices_count} office(s) under ${p.root?.name ?? 'your agency'}.`
                : 'No offices yet.'}{' '}
              Add, rename or move offices on the Offices page. If you are starting fresh, the setup
              wizard asks you a few questions and builds the list for you.
            </p>
            <div className="row">
              <Link className="btn btn-primary" to="/structure">
                Open the offices
              </Link>
              <Link className="btn" to="/setup">
                Use the setup wizard
              </Link>
            </div>
          </div>
        )}

        {active === 'year' && (
          <div className="stack">
            <p>
              {p.fiscal_year
                ? `You are monitoring ${p.fiscal_year.label}. To monitor another year, add it on the Years page.`
                : 'No year yet. Add the year you are monitoring.'}
            </p>
            <div className="row">
              <Link className="btn btn-primary" to="/fiscal-years">
                {p.fiscal_year ? 'Open the years' : 'Add the year'}
              </Link>
            </div>
          </div>
        )}

        {active === 'plans' && (
          <div className="stack">
            {!p.fiscal_year ? (
              <p>Set up the year first (step 2).</p>
            ) : (
              <>
                <p>
                  Open each office below and type in its plan. When an office's plan is complete,
                  mark it as final. Tip: the plan page can also read a filled-in Excel template.
                </p>
                <table className="table step-table">
                  <thead>
                    <tr>
                      <th>Office</th>
                      <th>Plan</th>
                      <th>Activities</th>
                      <th>Output targets</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {p.plans.map((r) => (
                      <tr key={r.office.id}>
                        <td>
                          <strong>{r.office.code}</strong> {r.office.name}
                        </td>
                        <td>
                          <span
                            className={`step-status is-${r.status === 'approved' ? 'done' : r.status}`}
                          >
                            {PLAN_WORD[r.status]}
                          </span>
                        </td>
                        <td>{r.activities}</td>
                        <td>{r.indicators}</td>
                        <td className="row">
                          {r.plan_id ? (
                            <Link className="btn btn-small" to={`/plans/${r.plan_id}`}>
                              {r.status === 'approved' ? 'View plan' : 'Enter plan'}
                            </Link>
                          ) : (
                            <button
                              type="button"
                              className="btn btn-small btn-primary"
                              disabled={busy}
                              onClick={() => startPlan(r.office.id)}
                            >
                              Start plan
                            </button>
                          )}
                          {r.plan_id && r.status !== 'approved' && r.activities > 0 && (
                            <button
                              type="button"
                              className="btn btn-small btn-primary"
                              disabled={busy}
                              onClick={() => finishPlan(r.plan_id!, r.status, r.office.name)}
                            >
                              Mark as final
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        )}

        {active === 'results' && (
          <div className="stack">
            {!p.period ? (
              <p>Set up the year first (step 2).</p>
            ) : p.monthly.length === 0 ? (
              <p>No office has a final plan yet. Finish the plans first (step 3).</p>
            ) : (
              <>
                <p>
                  Results for <strong>{month}</strong>. Open each office, type in what it did this
                  month, save, then press <em>Submit report</em> to mark the office as done.
                </p>
                <table className="table step-table">
                  <thead>
                    <tr>
                      <th>Office</th>
                      <th>{month}</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {p.monthly.map((r) => (
                      <tr key={r.office.id}>
                        <td>
                          <strong>{r.office.code}</strong> {r.office.name}
                        </td>
                        <td>
                          <span
                            className={`step-status is-${['submitted', 'locked'].includes(r.status) ? 'done' : r.status}`}
                          >
                            {MONTH_WORD[r.status] ?? r.status}
                          </span>
                        </td>
                        <td>
                          <Link
                            className="btn btn-small"
                            to={`/reports?fy=${fyId}&office=${r.office.id}&period=${periodId}`}
                          >
                            {['submitted', 'locked'].includes(r.status)
                              ? 'View results'
                              : 'Enter results'}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="muted small">
                  {p.months.find((m) => m.id === periodId)?.offices_done ?? 0} of {p.monthly.length}{' '}
                  offices done for {month}.
                </p>
              </>
            )}
          </div>
        )}

        {active === 'review' && (
          <div className="stack">
            {!p.period ? (
              <p>Set up the year first (step 2).</p>
            ) : (
              <>
                <p>
                  Open the dashboard for {month} and check each office's figures. If something is
                  wrong, go back to step 4 and correct it.
                </p>
                <div className="row">
                  <Link className="btn" to={`/dashboard?fy=${fyId}&period=${periodId}`}>
                    Open the dashboard
                  </Link>
                  <Link className="btn" to={`/rankings?fy=${fyId}&period=${periodId}`}>
                    See the rankings
                  </Link>
                  {p.period.status === 'locked' ? (
                    <span className="step-status is-done">{month} is closed</span>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busy}
                      onClick={closeMonth}
                    >
                      Close {month}
                    </button>
                  )}
                </div>
                <p className="muted small">
                  Close the months in order: an earlier open month must be closed first.
                </p>
              </>
            )}
          </div>
        )}

        {active === 'report' && (
          <div className="stack">
            {!p.period || !p.root ? (
              <p>Set up the year first (step 2).</p>
            ) : (
              <>
                <p>Choose what to download. Files stay in Downloads so you can get them again.</p>
                <div className="step-choices">
                  <button
                    type="button"
                    className="step-choice"
                    onClick={() => setExporting('year')}
                  >
                    <strong>Over-all performance for the year</strong>
                    <span>
                      PowerPoint presentation: over-all performance based on activities and on
                      output indicators, each office, activities by month, and rankings.
                    </span>
                  </button>
                  <button
                    type="button"
                    className="step-choice"
                    onClick={() => setExporting('monthly')}
                  >
                    <strong>Monthly report</strong>
                    <span>Excel workbook or PowerPoint presentation for one month.</span>
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      <nav className="step-nav" aria-label="Steps">
        {prev ? (
          <button type="button" className="btn" onClick={() => go({ step: prev.key })}>
            ← Back: {prev.title}
          </button>
        ) : (
          <span />
        )}
        {next && (
          <button type="button" className="btn btn-primary" onClick={() => go({ step: next.key })}>
            Next: {next.title} →
          </button>
        )}
      </nav>

      {exporting && p.root && periodId && (
        <ExportDialog
          officeId={p.root.id}
          officeLabel={p.root.name}
          periods={periods}
          periodId={periodId}
          view="owner"
          canExportAgency
          initialFormat={exporting === 'year' ? 'year' : 'xlsx'}
          defaultTitle={`Over-all performance ${p.fiscal_year?.label ?? ''}`.trim()}
          onClose={() => setExporting(null)}
        />
      )}
    </section>
  );
}
