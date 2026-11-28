import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { Period } from '../../api/types';
import { errorMessage } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { monthYear } from '../../lib/format';
import { isPending, SLIDE_GROUPS, STATUS_LABEL, type Job, type SlideGroup } from './types';

export const JOB_POLL_MS = 2000;

type Scope = 'office' | 'subtree' | 'agency';
type Format = 'xlsx' | 'pptx' | 'year';

/** Export dialog (P9.4, P10.3): format, scope, month (and slide groups for a deck); queues the
 * export and follows the job. Scores are always each office's own plan (D49). */
export default function ExportDialog({
  officeId,
  officeLabel,
  periods,
  periodId,
  canExportAgency,
  initialFormat = 'xlsx',
  defaultTitle = 'Over-all performance',
  onClose,
}: {
  officeId: string;
  officeLabel: string;
  periods: Period[];
  periodId: string;
  canExportAgency: boolean;
  initialFormat?: Format;
  defaultTitle?: string;
  onClose: () => void;
}) {
  const [format, setFormat] = useState<Format>(initialFormat);
  const [title, setTitle] = useState(defaultTitle);
  const [groups, setGroups] = useState<SlideGroup[]>(SLIDE_GROUPS.map((g) => g.key));
  const [scope, setScope] = useState<Scope>(
    initialFormat === 'year' && canExportAgency ? 'agency' : 'office',
  );
  const [month, setMonth] = useState(periodId);
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
      const body = { scope, office_id: officeId, period_id: month };
      setJob(
        format === 'year'
          ? await api.post<Job>('exports/pptx', { ...body, style: 'year', title })
          : await api.post<Job>(
              `exports/${format}`,
              format === 'pptx'
                ? {
                    ...body,
                    groups: SLIDE_GROUPS.map((g) => g.key).filter((k) => groups.includes(k)),
                  }
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
            Every file also stays in <Link to="/exports">Downloads</Link>.
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
              Excel workbook (one sheet per office, with calculations)
            </label>
            <label className="check">
              <input
                type="radio"
                name="format"
                checked={format === 'pptx'}
                onChange={() => setFormat('pptx')}
              />
              PowerPoint presentation for the month (ready to share)
            </label>
            <label className="check">
              <input
                type="radio"
                name="format"
                checked={format === 'year'}
                onChange={() => setFormat('year')}
              />
              Over-all performance for the year (PowerPoint, based on activities and on output
              indicators, with rankings)
            </label>
          </fieldset>
          {format === 'year' && (
            <label>
              Title on the first slide
              <input value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
            </label>
          )}
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
            {format === 'year' ? 'Figures as of the end of' : 'Month'}
            <select value={month} onChange={(e) => setMonth(e.target.value)}>
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {monthYear(p.start_date)}
                  {p.status === 'locked' ? ' (final)' : ' (not final)'}
                </option>
              ))}
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
              {format === 'xlsx' ? 'Prepare workbook' : 'Prepare presentation'}
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}
