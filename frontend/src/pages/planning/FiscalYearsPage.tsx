import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { FiscalYear } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { useAuth } from '../../auth/useAuth';
import { monthYear } from '../../lib/format';

const STATUS_HELP = {
  draft: 'Being prepared: plans can be entered, nothing is reported yet.',
  open: 'In use: plans are final and months are entered.',
  closed: 'Finished: kept for reference.',
};

export default function FiscalYearsPage() {
  const { me } = useAuth();
  const years = useResource<FiscalYear[]>('fiscal-years');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = me?.is_agency_admin ?? false;

  async function setStatus(fy: FiscalYear, status: FiscalYear['status']) {
    const what =
      status === 'open'
        ? `Open ${fy.label}? You can then enter the monthly results.`
        : `Close ${fy.label}? It stays available for viewing and exports.`;
    if (!window.confirm(what)) return;
    try {
      await api.patch(`fiscal-years/${fy.id}`, { status });
      years.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <section className="page">
      <div className="page-header">
        <h1>Years</h1>
        {isAdmin && (
          <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
            New fiscal year
          </button>
        )}
      </div>
      <FormError message={error ?? years.error} />
      {years.data?.length === 0 && (
        <p className="notice">
          No fiscal years yet.{isAdmin ? ' Create one to start entering plans.' : ''}
        </p>
      )}
      {years.data && years.data.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Fiscal year</th>
              <th>Months</th>
              <th>Status</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {years.data.map((fy) => (
              <tr key={fy.id}>
                <td>
                  <Link to={`/fiscal-years/${fy.id}`}>
                    <strong>{fy.label}</strong>
                  </Link>
                </td>
                <td>
                  {monthYear(fy.start_date)} – {monthYear(fy.end_date)}
                </td>
                <td title={STATUS_HELP[fy.status]}>
                  <span className={`chip chip-fy-${fy.status}`}>{fy.status}</span>
                </td>
                <td className="actions">
                  {isAdmin && fy.status === 'draft' && (
                    <button
                      type="button"
                      className="btn btn-small"
                      onClick={() => setStatus(fy, 'open')}
                    >
                      Open
                    </button>
                  )}
                  {isAdmin && fy.status === 'open' && (
                    <button
                      type="button"
                      className="btn btn-small"
                      onClick={() => setStatus(fy, 'closed')}
                    >
                      Close
                    </button>
                  )}
                  {isAdmin && fy.status === 'closed' && (
                    <button
                      type="button"
                      className="btn btn-small"
                      onClick={() => setStatus(fy, 'open')}
                    >
                      Reopen
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {creating && (
        <CreateDialog
          onClose={() => setCreating(false)}
          onDone={years.reload}
          startMonth={me?.agency.fiscal_year_start_month ?? 1}
        />
      )}
    </section>
  );
}

function CreateDialog({
  onClose,
  onDone,
  startMonth,
}: {
  onClose: () => void;
  onDone: () => void;
  startMonth: number;
}) {
  const nextYear = new Date().getFullYear() + 1;
  const [label, setLabel] = useState(String(nextYear));
  const [startYear, setStartYear] = useState(nextYear);
  const [error, setError] = useState<string | null>(null);
  const start = `${startYear}-${String(startMonth).padStart(2, '0')}-01`;

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post('fiscal-years', { label, start_year: startYear });
      onDone();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <Modal title="New fiscal year" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <label>
          Label
          <input value={label} onChange={(e) => setLabel(e.target.value)} />
        </label>
        <label>
          Starts in the year
          <input
            type="number"
            value={startYear}
            onChange={(e) => setStartYear(Number(e.target.value))}
          />
        </label>
        <p className="muted small">
          Runs for twelve months from {monthYear(start)} (your agency's fiscal year starts in that
          month).
        </p>
        <p className="muted small">Scores are worked out the same way as the Excel workbook.</p>
        <FormError message={error} />
        <div className="row">
          <button type="submit" className="btn btn-primary">
            Create
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
