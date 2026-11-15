import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { API_BASE, api } from '../../api/client';
import { errorMessage } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { JOB_POLL_MS } from './ExportDialog';
import { isPending, STATUS_LABEL, type Job } from './types';

interface ImportIssue {
  row: number | null;
  column: string;
  message: string;
}

/** Plan import (P9.7): template download, upload, then the job's result or its row-by-row errors. */
export default function ImportPlanDialog({
  office,
  fiscalYear,
  onClose,
  onImported,
}: {
  office: { id: string; code: string; name: string };
  fiscalYear: { id: string; label: string };
  onClose: () => void;
  onImported: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
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
        .then((j) => {
          setJob(j);
          if (j.status === 'done') onImported();
        })
        .catch((err: unknown) => setError(errorMessage(err)));
    }, JOB_POLL_MS);
    return () => window.clearInterval(timer);
  }, [jobId, pending, onImported]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    form.append('office_id', office.id);
    form.append('fiscal_year_id', fiscalYear.id);
    setBusy(true);
    setError(null);
    try {
      setJob(await api.post<Job>('imports/plan', form));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const template = `${API_BASE}/imports/plan-template?fiscal_year_id=${fiscalYear.id}&office_id=${office.id}`;
  const errors = (job?.result?.errors as ImportIssue[] | undefined) ?? [];
  const warnings = (job?.result?.warnings as ImportIssue[] | undefined) ?? [];
  const planId = job?.result?.plan_id as string | undefined;

  return (
    <Modal title={`Import a plan · ${office.code} · ${fiscalYear.label}`} onClose={onClose} wide>
      {job ? (
        <div className="stack" aria-live="polite">
          <p>
            <span className={`job-status job-${job.status}`}>{STATUS_LABEL[job.status]}</span>
            {pending && ' Reading the file…'}
            {job.status === 'done' && ' The draft plan was created.'}
          </p>
          {job.status === 'failed' && (
            <>
              <p className="form-error">{job.error}</p>
              {errors.length > 0 && <IssueTable issues={errors} caption="Problems to fix" />}
              <div className="row">
                <button type="button" className="btn" onClick={() => setJob(null)}>
                  Try another file
                </button>
              </div>
            </>
          )}
          {job.status === 'done' && planId && (
            <>
              {warnings.length > 0 && <IssueTable issues={warnings} caption="Worth checking" />}
              <p>
                <Link className="btn btn-primary" to={`/plans/${planId}`}>
                  Open the draft plan
                </Link>
              </p>
            </>
          )}
          <FormError message={error} />
        </div>
      ) : (
        <form className="stack" onSubmit={submit}>
          <p>
            Fill in the{' '}
            <a href={template} download>
              import template
            </a>{' '}
            (the same layout as the Excel export), or use an exported office sheet. The file becomes
            a <strong>draft</strong> plan for {office.name}; nothing is imported if any row has a
            problem.
          </p>
          <label>
            Excel file (.xlsx)
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <FormError message={error} />
          <div className="row">
            <button type="button" className="btn" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={!file || busy}>
              Import
            </button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function IssueTable({ issues, caption }: { issues: ImportIssue[]; caption: string }) {
  return (
    <table className="table compact">
      <caption>{caption}</caption>
      <thead>
        <tr>
          <th scope="col">Row</th>
          <th scope="col">Column</th>
          <th scope="col">Problem</th>
        </tr>
      </thead>
      <tbody>
        {issues.map((i, n) => (
          <tr key={n}>
            <td>{i.row ?? '—'}</td>
            <td>{i.column || '—'}</td>
            <td>{i.message}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
