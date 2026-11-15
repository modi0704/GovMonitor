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
type Format = 'xlsx' | 'pptx';

export const SLIDE_GROUPS = [
  { key: 'overall', label: 'Overall performance' },
  { key: 'offices', label: 'One slide per office' },
  { key: 'rankings', label: 'Rankings' },
  { key: 'indicators', label: 'Indicator tables' },
] as const;
type SlideGroup = (typeof SLIDE_GROUPS)[number]['key'];

/** Export dialog (P9.4, P10.3): format, scope, month, view (and slide groups for a deck); queues
 * the export and follows the job. */
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
  const [format, setFormat] = useState<Format>('xlsx');
  const [groups, setGroups] = useState<SlideGroup[]>(SLIDE_GROUPS.map((g) => g.key));
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
      const body = { scope, office_id: officeId, period_id: month, view: chosenView };
      setJob(
        await api.post<Job>(
          `exports/${format}`,
          format === 'pptx'
            ? { ...body, groups: SLIDE_GROUPS.map((g) => g.key).filter((k) => groups.includes(k)) }
            : body,
        ),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="Export" onClose={onClose}>
      {job ? (
        <div className="stack" aria-live="polite">
          <p>
            <span className={`job-status job-${job.status}`}>{STATUS_LABEL[job.status]}</span>
            {pending && ' The file is being prepared. You can close this window.'}
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
            <legend>Format</legend>
            <label className="check">
              <input
                type="radio"
                name="format"
                checked={format === 'xlsx'}
                onChange={() => setFormat('xlsx')}
              />
              Excel workbook (one sheet per office, live formulas)
            </label>
            <label className="check">
              <input
                type="radio"
                name="format"
                checked={format === 'pptx'}
                onChange={() => setFormat('pptx')}
              />
              PowerPoint deck (ready to present)
            </label>
          </fieldset>
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
          {format === 'pptx' && (
            <fieldset className="stack">
              <legend>Slides</legend>
              {SLIDE_GROUPS.map((g) => (
                <label key={g.key} className="check">
                  <input
                    type="checkbox"
                    checked={groups.includes(g.key)}
                    onChange={(e) =>
                      setGroups((cur) =>
                        e.target.checked ? [...cur, g.key] : cur.filter((k) => k !== g.key),
                      )
                    }
                  />
                  {g.label}
                </label>
              ))}
              <p className="muted small">The title and notes slides are always included.</p>
            </fieldset>
          )}
          <FormError message={error} />
          <div className="row">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={busy || (format === 'pptx' && groups.length === 0)}
            >
              {format === 'pptx' ? 'Prepare deck' : 'Prepare workbook'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
