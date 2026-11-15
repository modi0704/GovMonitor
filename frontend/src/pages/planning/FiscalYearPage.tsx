import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { FiscalYear, Period } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';
import { dateTime, monthYear } from '../../lib/format';

/** datetime-local value (browser time) for an ISO instant. */
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** A fiscal year's months: status and cutoff calendar (P7.2). */
export default function FiscalYearPage() {
  const { fyId } = useParams();
  const { me } = useAuth();
  const fy = useResource<FiscalYear>(`fiscal-years/${fyId}`);
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const isAdmin = me?.is_agency_admin ?? false;

  async function save(p: Period) {
    try {
      await api.patch(`periods/${p.id}`, { cutoff_at: new Date(editing[p.id]!).toISOString() });
      const next = { ...editing };
      delete next[p.id];
      setEditing(next);
      fy.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="page">
      <p className="breadcrumb">
        <Link to="/fiscal-years">Fiscal years</Link> › {fy.data?.label}
      </p>
      <div className="page-header">
        <h1>Fiscal year {fy.data?.label}</h1>
        {fy.data && <Link to={`/fiscal-years/${fy.data.id}/scoring`}>Scoring settings</Link>}
      </div>
      <p className="muted">
        Reports for each month are due at its cutoff. The default comes from the cutoff day in the
        scoring settings;
        {isAdmin
          ? ' you can move it for a single month here.'
          : ' the agency administrator can move it for a single month.'}
      </p>
      <FormError message={error ?? fy.error} />
      <table className="table">
        <thead>
          <tr>
            <th>Month</th>
            <th>Status</th>
            <th>Cutoff</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {fy.data?.periods?.map((p) => (
            <tr key={p.id}>
              <td>{monthYear(p.start_date)}</td>
              <td>
                <span
                  className={`chip ${p.status === 'locked' ? 'chip-sub-locked' : 'chip-fy-open'}`}
                >
                  {p.status === 'locked' ? `locked ${dateTime(p.locked_at)}` : 'open'}
                </span>
              </td>
              <td>
                {editing[p.id] !== undefined ? (
                  <input
                    type="datetime-local"
                    aria-label={`Cutoff for ${monthYear(p.start_date)}`}
                    value={editing[p.id]}
                    onChange={(e) => setEditing({ ...editing, [p.id]: e.target.value })}
                  />
                ) : (
                  dateTime(p.cutoff_at)
                )}
              </td>
              <td className="actions">
                {isAdmin && p.status === 'open' && editing[p.id] === undefined && (
                  <button
                    type="button"
                    className="btn btn-small"
                    onClick={() => setEditing({ ...editing, [p.id]: toLocalInput(p.cutoff_at) })}
                  >
                    Change cutoff
                  </button>
                )}
                {editing[p.id] !== undefined && (
                  <>
                    <button
                      type="button"
                      className="btn btn-small btn-primary"
                      onClick={() => save(p)}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      className="btn btn-small"
                      onClick={() => {
                        const next = { ...editing };
                        delete next[p.id];
                        setEditing(next);
                      }}
                    >
                      Cancel
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
