import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { Period } from '../../api/types';
import { errorMessage } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { monthYear } from '../../lib/format';
import { isPending, STATUS_LABEL, type Job } from './types';

export const JOB_POLL_MS = 2000;

type Scope = 'office' | 'subtree' | 'agency';

/** Export dialog (P9.4): scope, month and view; queues the workbook and follows the job. */
export default function ExportDialog({
  officeId,
  officeLabel,
  periods,
  periodId,
  view,
  canExportAgency,
  onClose,
}: {
  officeId: string;
  officeLabel: string;
  periods: Period[];
  periodId: string;
  view: 'owner' | 'implementing';
  canExportAgency: boolean;
  onClose: () => void;
}) {
  const [scope, setScope] = useState<Scope>('office');
  const [month, setMonth] = useState(periodId);
  const [chosenView, setChosenView] = useState(view);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const jobId = job?.id;
  const pending = job ? isPending(job) : false;
  useEffect(() => {
    if (!jobId || !pending) return;
    const timer = window.setInterval(() => {
      api
        .get<Job>(`jobs/${jobId}`)
        .then(setJob)
        .catch((err: unknown) => setError(errorMessage(err)));
    }, JOB_POLL_MS);
    return () => window.clearInterval(timer);
  }, [jobId, pending]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setJob(
        await api.post<Job>('exports/xlsx', {
          scope,
          office_id: officeId,
          period_id: month,
          view: chosenView,
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Export to Excel" onClose={onClose}>
      {job ? (
        <div className="stack" aria-live="polite">
          <p>
            <span className={`job-status job-${job.status}`}>{STATUS_LABEL[job.status]}</span>
            {pending && ' The workbook is being prepared. You can close this window.'}
          </p>
          {job.status === 'failed' && <p className="form-error">{job.error}</p>}
          {job.download_url && (
            <p>
              <a className="btn btn-primary" href={job.download_url} download>
                Download {job.file_name}
              </a>
            </p>
          )}
          <p className="muted small">
            Every export also stays in <Link to="/exports">My exports</Link>.
          </p>
          <FormError message={error} />
        </div>
      ) : (
        <form onSubmit={submit} className="stack">
          <fieldset className="stack">
            <legend>What to include</legend>
            <label className="check">
              <input
                type="radio"
                name="scope"
                checked={scope === 'office'}
                onChange={() => setScope('office')}
              />
              {officeLabel} only
            </label>
            <label className="check">
              <input
                type="radio"
                name="scope"
                checked={scope === 'subtree'}
                onChange={() => setScope('subtree')}
              />
              {officeLabel} and every office beneath it
            </label>
            {canExportAgency && (
              <label className="check">
                <input
                  type="radio"
                  name="scope"
                  checked={scope === 'agency'}
                  onChange={() => setScope('agency')}
                />
                The whole agency
              </label>
            )}
          </fieldset>
          <label>
            Month
            <select value={month} onChange={(e) => setMonth(e.target.value)}>
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {monthYear(p.start_date)}
                  {p.status === 'locked' ? ' (final)' : ' (provisional)'}
                </option>
              ))}
            </select>
          </label>
          <label>
            Scores of
            <select
              value={chosenView}
              onChange={(e) => setChosenView(e.target.value as 'owner' | 'implementing')}
            >
              <option value="owner">Each office's own plan (with offices beneath)</option>
              <option value="implementing">Activities each office carries out</option>
            </select>
          </label>
          <FormError message={error} />
          <div className="row">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={busy}>
              Prepare workbook
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
