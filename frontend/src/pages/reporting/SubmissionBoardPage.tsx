import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { FiscalYear } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { useAuth } from '../../auth/useAuth';
import { dateTime, monthYear } from '../../lib/format';

interface BoardRow {
  office: { id: string; code: string; name: string; depth: number };
  plan_version: number;
  status: 'draft' | 'submitted' | 'returned' | 'locked';
  submitted_at?: string | null;
  submitted_by?: string | null;
  return_note?: string;
}

interface Board {
  period: {
    id: string;
    start_date: string;
    cutoff_at: string;
    status: 'open' | 'locked';
    locked_at: string | null;
    locked_by: string | null;
    days_to_cutoff: number;
    can_lock: boolean;
    can_unlock: boolean;
  };
  offices: BoardRow[];
  not_submitted: { id: string; code: string; name: string }[];
}

const STATUS = {
  draft: 'Not submitted',
  submitted: 'Submitted',
  returned: 'Returned',
  locked: 'Locked',
};

/** Submission board (P7.6): every office's status for one month; return, lock, unlock. */
export default function SubmissionBoardPage() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const years = useResource<FiscalYear[]>('fiscal-years');
  const fyId =
    params.get('fy') ??
    years.data?.find((y) => y.status === 'open')?.id ??
    years.data?.[0]?.id ??
    null;
  const fy = useResource<FiscalYear>(fyId ? `fiscal-years/${fyId}` : null);
  const periods = fy.data?.periods ?? [];
  const periodId =
    params.get('period') ?? periods.find((p) => p.status === 'open')?.id ?? periods[0]?.id ?? null;
  const board = useResource<Board>(periodId ? `submission-board?period=${periodId}` : null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (me && !me.is_agency_admin) {
    return (
      <section className="page">
        <p className="notice">Only the agency administrator manages submissions and locking.</p>
      </section>
    );
  }

  async function run(fn: () => Promise<unknown>, done: string) {
    setError(null);
    // Stay on the month just acted on: without this, locking it would make the board jump to the
    // next open month.
    if (board.data && !params.get('period'))
      setParams({ fy: fyId ?? '', period: board.data.period.id });
    try {
      await fn();
      setNotice(done);
      board.reload();
      fy.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const b = board.data;
  const month = b ? monthYear(b.period.start_date) : '';

  function lock() {
    if (!b) return;
    const missing = b.not_submitted.length;
    const warning = missing
      ? ` ${missing} office(s) have not submitted. Their current figures will still be included.`
      : '';
    if (
      !window.confirm(
        `Lock ${month}? This makes the month's results final for every office and stops report changes.${warning}`,
      )
    )
      return;
    run(() => api.post(`periods/${b.period.id}/lock`), `${month} is locked.`);
  }

  function unlock() {
    if (!b) return;
    const reason = window.prompt(
      `Why reopen ${month}? Offices can change their reports again. Final figures will be recalculated, and a copy of the previous results stays in the audit log.`,
    );
    if (!reason) return;
    run(() => api.post(`periods/${b.period.id}/unlock`, { reason }), `${month} is unlocked.`);
  }

  function returnReport(row: BoardRow) {
    const note = window.prompt(`What should ${row.office.code} correct?`);
    if (!note || !b) return;
    run(
      () => api.post('reports/return', { office: row.office.id, period: b.period.id, note }),
      `Returned to ${row.office.code}.`,
    );
  }

  return (
    <section className="page page-wide">
      <div className="page-header">
        <h1>Submissions</h1>
        <div className="row">
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
          <label className="inline">
            Month
            <select
              value={periodId ?? ''}
              onChange={(e) => setParams({ fy: fyId ?? '', period: e.target.value })}
            >
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {monthYear(p.start_date)}
                  {p.status === 'locked' ? ' (locked)' : ''}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      <FormError message={error ?? board.error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {b && (
        <>
          <div className="report-head">
            <div>
              {b.period.status === 'locked' ? (
                <span className="chip chip-sub-locked">
                  Locked {dateTime(b.period.locked_at)} by {b.period.locked_by}
                </span>
              ) : (
                <span
                  className={`chip ${b.period.days_to_cutoff < 0 ? 'status-delayed' : 'chip-fy-open'}`}
                >
                  {b.period.days_to_cutoff >= 0
                    ? `Due in ${b.period.days_to_cutoff} day(s)`
                    : `Deadline passed ${-b.period.days_to_cutoff} day(s) ago`}
                </span>
              )}{' '}
              <span className="muted small">Report deadline {dateTime(b.period.cutoff_at)}</span>
            </div>
            <div className="row">
              {b.period.status === 'open' && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={lock}
                  disabled={!b.period.can_lock}
                  title={b.period.can_lock ? '' : 'Earlier months must be locked first'}
                >
                  Lock {month}
                </button>
              )}
              {b.period.can_unlock && (
                <button type="button" className="btn btn-danger" onClick={unlock}>
                  Unlock {month}
                </button>
              )}
            </div>
          </div>
          {b.period.status === 'open' && !b.period.can_lock && (
            <p className="muted small">Earlier months must be locked before this one.</p>
          )}
          {b.not_submitted.length > 0 && b.period.status === 'open' && (
            <div className="form-message">
              <strong>Not submitted yet ({b.not_submitted.length}):</strong>{' '}
              {b.not_submitted.map((o) => o.code).join(', ')}
            </div>
          )}
          {b.offices.length === 0 ? (
            <p className="notice">
              No office has an approved plan for this year yet. Approve plans on the Approvals page;
              each office with an approved plan then appears here every month.
            </p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Office</th>
                  <th>Status</th>
                  <th>Submitted</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {b.offices.map((r) => (
                  <tr key={r.office.id}>
                    <td style={{ paddingLeft: `${0.75 + r.office.depth * 0.9}rem` }}>
                      <span className="code">{r.office.code}</span> {r.office.name}
                    </td>
                    <td>
                      <span className={`chip chip-sub-${r.status}`}>{STATUS[r.status]}</span>
                      {r.status === 'returned' && r.return_note && (
                        <div className="muted small">{r.return_note}</div>
                      )}
                    </td>
                    <td>
                      {r.submitted_at ? `${dateTime(r.submitted_at)} · ${r.submitted_by}` : '—'}
                    </td>
                    <td className="actions">
                      <Link
                        className="btn btn-small"
                        to={`/reports?fy=${fyId}&office=${r.office.id}&period=${b.period.id}`}
                      >
                        Open report
                      </Link>
                      {r.status === 'submitted' && (
                        <button
                          type="button"
                          className="btn btn-small"
                          onClick={() => returnReport(r)}
                        >
                          Return
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
