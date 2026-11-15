import { useState } from 'react';
import { useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import Modal from '../../components/Modal';
import { monthName, percent } from '../../lib/format';
import type { DashActivity } from './types';

const KIND_WORD = {
  ahead: 'Ahead',
  on_time: 'On time',
  delayed: 'Behind',
  no_target: 'No target',
} as const;

interface History {
  activity: {
    code: string;
    title: string;
    unit: string;
    annual_target: string;
    owner_office: { code: string };
    implementing_office: { code: string };
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
                <th>Variance</th>
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
                        {KIND_WORD[a.status_kind]}
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
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Modal>
  );
}
