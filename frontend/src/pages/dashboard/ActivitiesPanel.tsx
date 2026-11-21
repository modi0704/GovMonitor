import { useState } from 'react';
import { errorMessage, useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { monthName, percent } from '../../lib/format';
import { ACCEPT, uploadMov } from '../reporting/movUpload';
import { ACTIVITY_STATUS_WORD } from '../../lib/statusWords';
import type { DashActivity } from './types';

interface History {
  activity: {
    code: string;
    title: string;
    unit: string;
    annual_target: string;
    owner_office: { code: string };
    implementing_office: { code: string };
    lineage_id: string;
  };
  months: {
    month_index: number;
    start_date: string;
    status: string;
    planned: string;
    actual: string | null;
    remarks: string;
    delay_reason: string;
    files: { id: string; file_name: string; download_url: string }[];
    period_id: string;
    can_attach: boolean;
  }[];
}

/** Activity list behind an office's figures, then one activity's months and files (P8.3). */
export default function ActivitiesPanel({
  officeId,
  periodId,
  view,
}: {
  officeId: string;
  periodId: string;
  view: string;
}) {
  const list = useResource<{ activities: DashActivity[] }>(
    `dashboard/activities?office=${officeId}&period=${periodId}&view=${view}`,
  );
  const [open, setOpen] = useState<DashActivity | null>(null);
  const rows = list.data?.activities ?? [];

  return (
    <div className="card">
      <FormError message={list.error} />
      {list.loading && <p>Loading…</p>}
      {!list.loading && rows.length === 0 && (
        <p className="muted">No activities for this office and view.</p>
      )}
      {rows.length > 0 && (
        <div className="table-scroll">
          <table className="table compact">
            <thead>
              <tr>
                <th>Activity</th>
                <th>{view === 'implementing' ? 'For office' : 'Carried out by'}</th>
                <th>Weight</th>
                <th>Target to date</th>
                <th>Done to date</th>
                <th>Gap</th>
                <th>Status</th>
                <th>Reason for delay</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.lineage_id}>
                  <td>
                    <button type="button" className="btn-link-plain" onClick={() => setOpen(a)}>
                      <span className="code">{a.code}</span> {a.title}
                    </button>
                  </td>
                  <td>
                    {view === 'implementing' ? a.owner_office_code : a.implementing_office_code}
                  </td>
                  <td>{percent(a.weight)}</td>
                  <td>
                    {a.cum_target} {a.unit}
                  </td>
                  <td>{a.cum_actual}</td>
                  <td>{a.no_target ? '—' : percent(a.variance)}</td>
                  <td>
                    {a.status_kind && (
                      <span
                        className={`chip status-${a.status_kind === 'no_target' ? 'on_time' : a.status_kind}`}
                      >
                        {ACTIVITY_STATUS_WORD[a.status_kind]}
                      </span>
                    )}
                  </td>
                  <td className="small">{a.delay_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {open && (
        <HistoryDialog
          lineageId={open.lineage_id}
          periodId={periodId}
          onClose={() => setOpen(null)}
        />
      )}
    </div>
  );
}

function HistoryDialog({
  lineageId,
  periodId,
  onClose,
}: {
  lineageId: string;
  periodId: string;
  onClose: () => void;
}) {
  const h = useResource<History>(`dashboard/activity?lineage=${lineageId}&period=${periodId}`);
  const a = h.data?.activity;
  return (
    <Modal title={a ? `${a.code} ${a.title}` : 'Activity'} onClose={onClose} wide>
      <FormError message={h.error} />
      {a && (
        <p className="muted small">
          Year target {a.annual_target} {a.unit} · plan of {a.owner_office.code} · carried out by{' '}
          {a.implementing_office.code}
        </p>
      )}
      {h.data && (
        <table className="table compact">
          <thead>
            <tr>
              <th>Month</th>
              <th>Planned</th>
              <th>Done</th>
              <th>Remarks / reason for delay</th>
              <th>Files</th>
            </tr>
          </thead>
          <tbody>
            {h.data.months.map((m) => (
              <tr key={m.month_index}>
                <td>
                  {monthName(m.start_date)}
                  {m.status === 'locked' ? ' ✓' : ''}
                </td>
                <td>{m.planned}</td>
                <td>{m.actual ?? '—'}</td>
                <td className="small">
                  {[m.remarks, m.delay_reason && `Delay: ${m.delay_reason}`]
                    .filter(Boolean)
                    .join(' · ')}
                </td>
                <td>
                  {m.files.map((f) => (
                    <a key={f.id} href={f.download_url} className="file-link">
                      {f.file_name}
                    </a>
                  ))}
                  {m.can_attach && a && (
                    <AttachButtons
                      lineageId={a.lineage_id}
                      periodId={m.period_id}
                      month={monthName(m.start_date)}
                      onDone={h.reload}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Modal>
  );
}

/** Phone-friendly upload (P12.2): take a photo with the camera or choose a file; same endpoint and
 * rules as the desktop upload. */
function AttachButtons({
  lineageId,
  periodId,
  month,
  onDone,
}: {
  lineageId: string;
  periodId: string;
  month: string;
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function upload(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await uploadMov(
        { targetType: 'activity_actual', lineageId, periodId, label: month, editable: true },
        file,
      );
      onDone();
    } catch (err) {
      setError(errorMessage(err, 'The file could not be attached.'));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="attach-buttons">
      <label className="btn btn-small">
        Take photo
        <input
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          disabled={busy}
          aria-label={`Take a photo for ${month}`}
          onChange={(e) => upload(e.target.files)}
        />
      </label>
      <label className="btn btn-small">
        Choose file
        <input
          type="file"
          accept={ACCEPT}
          className="sr-only"
          disabled={busy}
          aria-label={`Choose a file for ${month}`}
          onChange={(e) => upload(e.target.files)}
        />
      </label>
      {busy && <span className="muted small">Uploading…</span>}
      {error && <span className="form-error small">{error}</span>}
    </div>
  );
}
