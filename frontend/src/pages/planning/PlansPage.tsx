import { useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { FiscalYear, OfficeRow, PlanSummary } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { money } from '../../lib/format';

const STATUS_LABEL = {
  draft: 'Draft',
  submitted: 'Waiting for approval',
  approved: 'Approved',
  superseded: 'Superseded',
};

/** Plans per office for one fiscal year; start a plan; open the editor (P5.3, P5.5). */
export default function PlansPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const years = useResource<FiscalYear[]>('fiscal-years');
  const offices = useResource<OfficeRow[]>('offices?include_inactive=0');
  const fyId =
    params.get('fy') ??
    years.data?.find((y) => y.status !== 'closed')?.id ??
    years.data?.[0]?.id ??
    null;
  const plans = useResource<PlanSummary[]>(fyId ? `plans?fiscal_year=${fyId}` : null);
  const [error, setError] = useState<string | null>(null);

  const byOffice = useMemo(() => {
    const map = new Map<string, PlanSummary[]>();
    plans.data?.forEach((p) => map.set(p.office.id, [...(map.get(p.office.id) ?? []), p]));
    return map;
  }, [plans.data]);

  async function start(office: OfficeRow) {
    if (!fyId) return;
    try {
      const plan = await api.post<{ id: string }>('plans', {
        office_id: office.id,
        fiscal_year_id: fyId,
      });
      navigate(`/plans/${plan.id}`);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="page page-wide">
      <div className="page-header">
        <h1>Plans</h1>
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
      <FormError message={error ?? plans.error ?? years.error} />
      {years.data?.length === 0 && (
        <p className="notice">
          There is no fiscal year yet. The agency administrator creates one on the{' '}
          <Link to="/fiscal-years">Fiscal years</Link> page.
        </p>
      )}
      {fyId && offices.data && (
        <table className="table">
          <thead>
            <tr>
              <th>Office</th>
              <th>Plan</th>
              <th>Status</th>
              <th>Planned cost</th>
              <th>Approved budget</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {offices.data.map((o) => {
              const versions = byOffice.get(o.id) ?? [];
              const current =
                versions.find((p) => p.status !== 'superseded' && p.status !== 'approved') ??
                versions.find((p) => p.status === 'approved');
              return (
                <tr key={o.id}>
                  <td style={{ paddingLeft: `${0.75 + o.depth * 1}rem` }}>
                    <span className="code">{o.code}</span> {o.name}
                  </td>
                  <td>{current ? `Version ${current.version}` : '—'}</td>
                  <td>
                    {current ? (
                      <span className={`chip chip-plan-${current.status}`}>
                        {STATUS_LABEL[current.status]}
                      </span>
                    ) : (
                      <span className="muted small">No plan</span>
                    )}
                  </td>
                  <td>{current ? money(current.planned_cost) : ''}</td>
                  <td>{current?.approved_budget ? money(current.approved_budget) : ''}</td>
                  <td className="actions">
                    {current ? (
                      <Link className="btn btn-small" to={`/plans/${current.id}`}>
                        {current.can_edit ? 'Edit' : 'Open'}
                      </Link>
                    ) : (
                      o.can_edit && (
                        <button type="button" className="btn btn-small" onClick={() => start(o)}>
                          Start plan
                        </button>
                      )
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
