import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { FiscalYear, PlanSummary } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';
import { dateTime, money } from '../../lib/format';

/** Plan approval queue and budget vs planned cost per office (P5.8). Agency administrator. */
export default function ApprovalsPage() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const years = useResource<FiscalYear[]>('fiscal-years');
  const fyId =
    params.get('fy') ??
    years.data?.find((y) => y.status !== 'closed')?.id ??
    years.data?.[0]?.id ??
    null;
  const plans = useResource<PlanSummary[]>(
    fyId ? `plans?fiscal_year=${fyId}&status=submitted,approved,draft` : null,
  );
  const [budgets, setBudgets] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  if (me && !me.is_agency_admin) {
    return (
      <section className="page">
        <p className="notice">Only the agency administrator approves plans.</p>
      </section>
    );
  }

  const all = plans.data ?? [];
  const queue = all.filter((p) => p.status === 'submitted');
  // One line per office: the version in force (approved) or the one being prepared.
  const current = new Map<string, PlanSummary>();
  all.forEach((p) => {
    const seen = current.get(p.office.id);
    if (!seen || (seen.status !== 'approved' && p.status === 'approved'))
      current.set(p.office.id, p);
  });

  async function act(plan: PlanSummary, path: 'approve' | 'return') {
    let body: unknown;
    if (path === 'approve') {
      if (
        !window.confirm(
          `Approve the ${plan.office.code} plan, version ${plan.version}? Monthly reports will be compared with its targets. This replaces any earlier approved plan.`,
        )
      )
        return;
    } else {
      const note = window.prompt(
        `Why is the ${plan.office.code} plan returned? The office sees this note.`,
      );
      if (!note) return;
      body = { note };
    }
    try {
      await api.post(`plans/${plan.id}/${path}`, body);
      plans.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function saveBudget(plan: PlanSummary) {
    try {
      await api.patch(`plans/${plan.id}`, { approved_budget: budgets[plan.id] ?? '' });
      plans.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="page page-wide">
      <div className="page-header">
        <h1>Plans to approve</h1>
        <label className="inline">
          Fiscal year
          <select value={fyId ?? ''} onChange={(e) => setParams({ fy: e.target.value })}>
            {years.data?.map((y) => (
              <option key={y.id} value={y.id}>
                {y.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <FormError message={error ?? plans.error} />
      <h2>Waiting for approval ({queue.length})</h2>
      {queue.length === 0 ? (
        <p className="muted">Nothing is waiting. Submitted plans appear here.</p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Office</th>
              <th>Version</th>
              <th>Submitted</th>
              <th>Planned cost</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {queue.map((p) => (
              <tr key={p.id}>
                <td>
                  <span className="code">{p.office.code}</span> {p.office.name}
                </td>
                <td>{p.version}</td>
                <td>
                  {dateTime(p.submitted_at)} · {p.submitted_by}
                </td>
                <td>{money(p.planned_cost)}</td>
                <td className="actions">
                  <Link className="btn btn-small" to={`/plans/${p.id}`}>
                    Review
                  </Link>
                  <button
                    type="button"
                    className="btn btn-small btn-primary"
                    onClick={() => act(p, 'approve')}
                  >
                    Approve
                  </button>
                  <button type="button" className="btn btn-small" onClick={() => act(p, 'return')}>
                    Return
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <h2>Budget vs planned cost</h2>
      <p className="muted small">
        The approved budget is the amount allocated to the office; planned cost is the total cost of
        its activities.
      </p>
      <table className="table">
        <thead>
          <tr>
            <th>Office</th>
            <th>Plan</th>
            <th>Approved budget</th>
            <th>Planned cost</th>
            <th>Difference</th>
          </tr>
        </thead>
        <tbody>
          {[...current.values()].map((p) => {
            const diff =
              p.approved_budget === null
                ? null
                : Number(p.approved_budget) - Number(p.planned_cost);
            return (
              <tr key={p.id}>
                <td>
                  <span className="code">{p.office.code}</span> {p.office.name}
                </td>
                <td>
                  v{p.version} · {p.status}
                </td>
                <td>
                  <form
                    className="row"
                    onSubmit={(e) => {
                      e.preventDefault();
                      saveBudget(p);
                    }}
                  >
                    <input
                      aria-label={`Approved budget, ${p.office.code}`}
                      inputMode="decimal"
                      value={budgets[p.id] ?? p.approved_budget ?? ''}
                      onChange={(e) => setBudgets({ ...budgets, [p.id]: e.target.value })}
                      style={{ maxWidth: '12rem' }}
                    />
                    {budgets[p.id] !== undefined && (
                      <button type="submit" className="btn btn-small">
                        Save
                      </button>
                    )}
                  </form>
                </td>
                <td>{money(p.planned_cost)}</td>
                <td className={diff !== null && diff < 0 ? 'text-delayed' : ''}>
                  {diff === null ? '—' : `${money(diff)}${diff < 0 ? ' over budget' : ''}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
