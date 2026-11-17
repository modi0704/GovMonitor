import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { FiscalYear, Preset } from '../../api/types';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { useAuth } from '../../auth/useAuth';
import { monthYear } from '../../lib/format';
import { scoringMethodDescription, scoringMethodName } from './scoringMethodText';

const STATUS_HELP = {
  draft: 'Being prepared: plans can be entered, nothing is reported yet.',
  open: 'In use: plans are approved and months are reported.',
  closed: 'Finished: kept for reference.',
};

export default function FiscalYearsPage() {
  const { me } = useAuth();
  const years = useResource<FiscalYear[]>('fiscal-years');
  const presets = useResource<Preset[]>('scoring-presets');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isAdmin = me?.is_agency_admin ?? false;

  async function setStatus(fy: FiscalYear, status: FiscalYear['status']) {
    const what =
      status === 'open'
        ? `Open ${fy.label}? Offices can then report their monthly accomplishments.`
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
        <h1>Fiscal years</h1>
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
              <th>Scoring</th>
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
                <td>
                  <Link to={`/fiscal-years/${fy.id}/scoring`}>{scoringMethodName(fy.preset)}</Link>
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
          presets={presets.data ?? []}
          onClose={() => setCreating(false)}
          onDone={years.reload}
          startMonth={me?.agency.fiscal_year_start_month ?? 1}
        />
      )}
    </section>
  );
}

function CreateDialog({
  presets,
  onClose,
  onDone,
  startMonth,
}: {
  presets: Preset[];
  onClose: () => void;
  onDone: () => void;
  startMonth: number;
}) {
  const nextYear = new Date().getFullYear() + 1;
  const [label, setLabel] = useState(String(nextYear));
  const [startYear, setStartYear] = useState(nextYear);
  const [preset, setPreset] = useState('workbook_compatible');
  const [error, setError] = useState<string | null>(null);
  const start = `${startYear}-${String(startMonth).padStart(2, '0')}-01`;

  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post('fiscal-years', { label, start_year: startYear, preset });
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
        <fieldset className="stack">
          <legend>Scoring method</legend>
          {presets.map((p) => (
            <label key={p.name} className="check">
              <input
                type="radio"
                name="preset"
                checked={preset === p.name}
                onChange={() => setPreset(p.name)}
              />
              <span>
                <strong>{scoringMethodName(p.name)}</strong>
                <br />
                <span className="muted small">{scoringMethodDescription(p.name)}</span>
              </span>
            </label>
          ))}
        </fieldset>
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
