import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { FiscalYear, Period } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { dateTime, monthYear } from '../../lib/format';

/** A year's months (P7.2, D49): close a month by hand when its figures are in, or reopen the
 * latest closed month to correct it. There are no deadlines and nothing closes by itself. */
export default function FiscalYearPage() {
  const { fyId } = useParams();
  const fy = useResource<FiscalYear>(`fiscal-years/${fyId}`);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const periods = fy.data?.periods ?? [];
  const firstOpen = periods.find((p) => p.status !== 'locked');
  const lastClosed = [...periods].reverse().find((p) => p.status === 'locked');

  async function run(call: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await call();
      setNotice(done);
      fy.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function close(p: Period) {
    const month = monthYear(p.start_date);
    if (!window.confirm(`Close ${month}? Its figures become final and can no longer be changed.`))
      return;
    void run(() => api.post(`periods/${p.id}/lock`), `${month} is closed. Its figures are final.`);
  }

  function reopen(p: Period) {
    const month = monthYear(p.start_date);
    const reason = window.prompt(`Why reopen ${month}? (kept in the change history)`);
    if (!reason) return;
    void run(
      () => api.post(`periods/${p.id}/unlock`, { reason }),
      `${month} is open again. Close it once the figures are corrected.`,
    );
  }

  return (
    <section className="page">
      <p className="breadcrumb">
        <Link to="/fiscal-years">Years</Link> › {fy.data?.label}
      </p>
      <div className="page-header">
        <h1>Year {fy.data?.label}</h1>
      </div>
      <p className="muted">
        Close each month when all its figures are in; closed figures are final. Months close only
        when you close them, one at a time and in order.
      </p>
      <FormError message={error ?? fy.error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <table className="table">
        <thead>
          <tr>
            <th>Month</th>
            <th>Status</th>
            <th aria-label="Actions" />
          </tr>
        </thead>
        <tbody>
          {periods.map((p) => (
            <tr key={p.id}>
              <td>{monthYear(p.start_date)}</td>
              <td>
                <span
                  className={`chip ${p.status === 'locked' ? 'chip-sub-locked' : 'chip-fy-open'}`}
                >
                  {p.status === 'locked' ? `closed ${dateTime(p.locked_at)}` : 'open'}
                </span>
              </td>
              <td className="actions">
                {fy.data?.status === 'open' && p.id === firstOpen?.id && (
                  <button
                    type="button"
                    className="btn btn-small"
                    onClick={() => close(p)}
                    disabled={busy}
                  >
                    Close month
                  </button>
                )}
                {p.id === lastClosed?.id && (
                  <button
                    type="button"
                    className="btn btn-small"
                    onClick={() => reopen(p)}
                    disabled={busy}
                  >
                    Reopen month
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
