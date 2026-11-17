import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useResource } from '../../api/useResource';
import { dateTime } from '../../lib/format';
import { isPending, KIND_LABEL, SCOPE_LABEL, STATUS_LABEL, type Job } from './types';

export const POLL_MS = 3000;

/** "My exports" (P9.1): the signed-in user's exports and imports, refreshed while any is running. */
export default function MyExportsPage() {
  const jobs = useResource<Job[]>('jobs');
  const pending = (jobs.data ?? []).some(isPending);
  const { reload } = jobs;

  useEffect(() => {
    if (!pending) return;
    const timer = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(timer);
  }, [pending, reload]);

  return (
    <section className="page">
      <h1>My exports</h1>
      <p className="muted">
        Exports are prepared in the background. Files stay here so you can download them again.
      </p>
      {jobs.error && <p className="form-error">{jobs.error}</p>}
      {jobs.loading && !jobs.data && <p>Loading…</p>}
      {jobs.data && jobs.data.length === 0 && (
        <p className="notice">Nothing yet. Use “Export” on the dashboard to make a workbook.</p>
      )}
      {jobs.data && jobs.data.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th scope="col">Requested</th>
              <th scope="col">Type</th>
              <th scope="col">Offices included</th>
              <th scope="col">Status</th>
              <th scope="col">File</th>
            </tr>
          </thead>
          <tbody>
            {jobs.data.map((job) => (
              <tr key={job.id}>
                <td>{dateTime(job.created_at)}</td>
                <td>{KIND_LABEL[job.kind] ?? job.kind}</td>
                <td>{SCOPE_LABEL[job.params.scope ?? ''] ?? '—'}</td>
                <td>
                  <span className={`job-status job-${job.status}`}>{STATUS_LABEL[job.status]}</span>
                  {job.status === 'failed' && job.error && (
                    <div className="muted small">{job.error}</div>
                  )}
                </td>
                <td>
                  {job.download_url ? (
                    <a href={job.download_url} download>
                      {job.file_name ?? 'Download'}
                    </a>
                  ) : job.kind === 'import_plan' && typeof job.result.plan_id === 'string' ? (
                    <Link to={`/plans/${job.result.plan_id}`}>Open the draft plan</Link>
                  ) : (
                    String(job.result.file_name ?? '—')
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
