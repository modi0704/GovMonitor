import { useEffect, useMemo, useState } from 'react';
import { API_BASE, api } from '../api/client';
import type { AuditPage as AuditPageData, AuditRow, OfficeRow, UserRow } from '../api/types';
import { errorMessage, useResource } from '../api/useResource';
import FormError from '../components/FormError';
import Modal from '../components/Modal';
import { useAuth } from '../auth/useAuth';
import { auditLabel } from '../lib/auditLabels';

interface Filters {
  from: string;
  to: string;
  actor: string;
  action: string;
  office: string;
  entity_type: string;
}

const EMPTY: Filters = { from: '', to: '', actor: '', action: '', office: '', entity_type: '' };

function query(filters: Filters, extra: Record<string, string> = {}): string {
  const qs = new URLSearchParams();
  Object.entries({ ...filters, ...extra }).forEach(([k, v]) => v && qs.set(k, v));
  return qs.toString();
}

function show(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/** Audit log (P3.5): agency administrator only. */
export default function AuditPage() {
  const { me } = useAuth();
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [applied, setApplied] = useState<Filters>(EMPTY);
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [nextBefore, setNextBefore] = useState<number | null>(null);
  const [options, setOptions] = useState<{ actions: string[]; entity_types: string[] }>({
    actions: [],
    entity_types: [],
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<AuditRow | null>(null);
  const users = useResource<UserRow[]>(me?.is_agency_admin ? 'users' : null);
  const offices = useResource<OfficeRow[]>(me?.is_agency_admin ? 'offices' : null);
  const officeName = useMemo(
    () => new Map((offices.data ?? []).map((o) => [o.id, `${o.code} ${o.name}`])),
    [offices.data],
  );

  useEffect(() => {
    let active = true;
    api
      .get<AuditPageData>(`audit-log?${query(applied)}`)
      .then((page) => {
        if (!active) return;
        setRows(page.results);
        setNextBefore(page.next_before);
        setOptions({ actions: page.actions, entity_types: page.entity_types });
        setError(null);
      })
      .catch((err: unknown) => active && setError(errorMessage(err)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [applied]);

  if (me && !me.is_agency_admin) {
    return (
      <section className="page">
        <h1>Change history</h1>
        <p className="notice">Only the agency administrator can view the audit log.</p>
      </section>
    );
  }

  async function more() {
    if (nextBefore === null) return;
    try {
      const page = await api.get<AuditPageData>(
        `audit-log?${query(applied, { before: String(nextBefore) })}`,
      );
      setRows([...rows, ...page.results]);
      setNextBefore(page.next_before);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function open(row: AuditRow) {
    try {
      setDetail(await api.get<AuditRow>(`audit-log/${row.id}`));
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const set = (k: keyof Filters) => (e: { target: { value: string } }) =>
    setFilters({ ...filters, [k]: e.target.value });

  return (
    <section className="page page-wide">
      <div className="page-header">
        <h1>Change history</h1>
        <a className="btn" href={`${API_BASE}/audit-log/export.csv?${query(applied)}`} download>
          Download CSV
        </a>
      </div>
      <p className="muted">
        Every sign-in and every change, newest first. Entries cannot be edited or deleted.
      </p>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setLoading(true);
          setApplied(filters);
        }}
      >
        <label>
          From
          <input type="date" value={filters.from} onChange={set('from')} />
        </label>
        <label>
          To
          <input type="date" value={filters.to} onChange={set('to')} />
        </label>
        <label>
          User
          <select value={filters.actor} onChange={set('actor')}>
            <option value="">Anyone</option>
            {users.data?.map((u) => (
              <option key={u.id} value={u.id}>
                {u.full_name || u.email}
              </option>
            ))}
          </select>
        </label>
        <label>
          Action
          <select value={filters.action} onChange={set('action')}>
            <option value="">Any</option>
            {options.actions.map((a) => (
              <option key={a} value={a}>
                {auditLabel(a)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Office
          <select value={filters.office} onChange={set('office')}>
            <option value="">Any</option>
            {offices.data?.map((o) => (
              <option key={o.id} value={o.id}>
                {'  '.repeat(o.depth)}
                {o.code} {o.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Record type
          <select value={filters.entity_type} onChange={set('entity_type')}>
            <option value="">Any</option>
            {options.entity_types.map((t) => (
              <option key={t} value={t}>
                {auditLabel(t)}
              </option>
            ))}
          </select>
        </label>
        <div className="row filter-buttons">
          <button type="submit" className="btn btn-primary">
            Apply
          </button>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setFilters(EMPTY);
              setApplied(EMPTY);
            }}
          >
            Clear
          </button>
        </div>
      </form>
      <FormError message={error} />
      {loading && <p>Loading…</p>}
      {!loading && rows.length === 0 && <p className="notice">No entries match these filters.</p>}
      {rows.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>When</th>
              <th>Who</th>
              <th>Action</th>
              <th>Record</th>
              <th>Office</th>
              <th>Changed</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="clickable" onClick={() => open(r)}>
                <td className="nowrap">{new Date(r.at).toLocaleString()}</td>
                <td>{r.actor}</td>
                <td>
                  <button type="button" className="btn-link-plain" onClick={() => open(r)}>
                    {auditLabel(r.action)}
                  </button>
                </td>
                <td>{auditLabel(r.entity_type)}</td>
                <td>{r.office_id ? (officeName.get(r.office_id) ?? '—') : '—'}</td>
                <td className="muted small">{r.changed.map(auditLabel).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {nextBefore !== null && (
        <button type="button" className="btn" onClick={more}>
          Show older entries
        </button>
      )}
      {detail && (
        <Modal
          title={`${auditLabel(detail.action)} · ${auditLabel(detail.entity_type || 'change')}`}
          onClose={() => setDetail(null)}
          wide
        >
          <p className="muted small">
            {new Date(detail.at).toLocaleString()} · {detail.actor} ({auditLabel(detail.actor_type)}
            ) · Connection address {detail.ip ?? '-'} · Reference {detail.request_id || '-'}
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Field</th>
                <th>Before</th>
                <th>After</th>
              </tr>
            </thead>
            <tbody>
              {detail.changed.map((field) => (
                <tr key={field}>
                  <td>{auditLabel(field)}</td>
                  <td>{show(detail.before?.[field])}</td>
                  <td>{show(detail.after?.[field])}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {detail.changed.length === 0 && (
            <p className="muted">No field values were recorded for this event.</p>
          )}
        </Modal>
      )}
    </section>
  );
}
