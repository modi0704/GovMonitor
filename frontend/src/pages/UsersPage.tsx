import { useState, type FormEvent } from 'react';
import { api } from '../api/client';
import type { OfficeRow, ScopeOffice, UserRow } from '../api/types';
import { errorMessage, useResource } from '../api/useResource';
import FormError from '../components/FormError';
import Modal from '../components/Modal';
import { useAuth } from '../auth/useAuth';

const LEVEL_LABEL = { admin: 'Admin', read_only: 'Read-only' } as const;

function accessSummary(u: UserRow): string {
  if (u.is_agency_admin) return 'Agency administrator';
  if (u.assignments.length === 0) return 'No access yet';
  return u.assignments.map((a) => `${LEVEL_LABEL[a.level]} · ${a.office.code}`).join(', ');
}

/** Users (P2.5): agency administrator only. */
export default function UsersPage() {
  const { me } = useAuth();
  const users = useResource<UserRow[]>('users');
  const offices = useResource<OfficeRow[]>('offices');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [secret, setSecret] = useState<{ email: string; password: string } | null>(null);
  const [filter, setFilter] = useState('');
  const selected = users.data?.find((u) => u.id === selectedId) ?? null;

  if (me && !me.is_agency_admin) {
    return (
      <section className="page">
        <h1>Users</h1>
        <p className="notice">Only the agency administrator can manage users.</p>
      </section>
    );
  }

  const f = filter.trim().toLowerCase();
  const shown = (users.data ?? []).filter(
    (u) => !f || u.email.includes(f) || u.full_name.toLowerCase().includes(f),
  );

  return (
    <section className="page page-wide">
      <div className="page-header">
        <h1>Users</h1>
        <button type="button" className="btn btn-primary" onClick={() => setCreating(true)}>
          Add user
        </button>
      </div>
      <p className="muted">
        Each user gets access at one or more offices, as <strong>Admin</strong> (can enter and
        change data) or <strong>Read-only</strong>. Access covers the office and every office
        beneath it.
      </p>
      {secret && (
        <div className="notice" role="status">
          Temporary password for <strong>{secret.email}</strong> (shown once):{' '}
          <code>{secret.password}</code>. Give it to them securely; they must choose their own at
          first sign-in.{' '}
          <button type="button" className="btn btn-link" onClick={() => setSecret(null)}>
            Hide
          </button>
        </div>
      )}
      <FormError message={users.error} />
      <input
        type="search"
        placeholder="Find by name or email"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        aria-label="Find users"
        className="search"
      />
      <div className="split">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Access</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((u) => (
              <tr
                key={u.id}
                className={`clickable ${u.id === selectedId ? 'selected' : ''}`}
                onClick={() => setSelectedId(u.id)}
              >
                <td>
                  <button
                    type="button"
                    className="btn-link-plain"
                    onClick={() => setSelectedId(u.id)}
                  >
                    {u.full_name || '—'}
                  </button>
                </td>
                <td>{u.email}</td>
                <td>{accessSummary(u)}</td>
                <td>
                  {u.is_active ? (
                    <span className="chip chip-active">active</span>
                  ) : (
                    <span className="chip chip-suspended">deactivated</span>
                  )}
                  {u.locked && <span className="chip chip-suspended">locked</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {selected && (
          <UserPanel
            key={selected.id}
            user={selected}
            offices={offices.data ?? []}
            isSelf={selected.id === me?.id}
            onChanged={users.reload}
            onSecret={(password) => setSecret({ email: selected.email, password })}
          />
        )}
      </div>
      {creating && (
        <CreateUserDialog
          offices={offices.data ?? []}
          onClose={() => setCreating(false)}
          onCreated={(u) => {
            users.reload();
            setSelectedId(u.id);
            if (u.temporary_password) setSecret({ email: u.email, password: u.temporary_password });
          }}
        />
      )}
    </section>
  );
}

function OfficeSelect({
  offices,
  value,
  onChange,
  label = 'Office',
}: {
  offices: OfficeRow[];
  value: string;
  onChange: (v: string) => void;
  label?: string;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Choose an office…</option>
        {offices.map((o) => (
          <option key={o.id} value={o.id}>
            {'  '.repeat(o.depth)}
            {o.code} {o.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function UserPanel({
  user,
  offices,
  isSelf,
  onChanged,
  onSecret,
}: {
  user: UserRow;
  offices: OfficeRow[];
  isSelf: boolean;
  onChanged: () => void;
  onSecret: (password: string) => void;
}) {
  const scope = useResource<ScopeOffice[]>(
    `users/${user.id}/scope?v=${user.assignments.length}-${user.assignments.map((a) => a.level).join()}`,
  );
  const [officeId, setOfficeId] = useState('');
  const [level, setLevel] = useState<'admin' | 'read_only'>('read_only');
  const [error, setError] = useState<string | null>(null);

  async function act(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <aside className="card side-panel" aria-label="Selected user">
      <h2>{user.full_name || user.email}</h2>
      <p className="muted small">
        {user.email} · last sign-in{' '}
        {user.last_login_at ? new Date(user.last_login_at).toLocaleString() : 'never'} · two-step{' '}
        {user.has_2fa ? 'on' : 'off'}
      </p>
      <FormError message={error} />
      <h3>Access</h3>
      {user.assignments.length === 0 && <p className="muted small">No access yet.</p>}
      <ul className="plain-list">
        {user.assignments.map((a) => (
          <li key={a.id} className="row-between">
            <span>
              <span className="code">{a.office.code}</span> {a.office.name}
            </span>
            <span className="row">
              <select
                aria-label={`Access level at ${a.office.name}`}
                value={a.level}
                onChange={(e) =>
                  act(() => api.patch(`role-assignments/${a.id}`, { level: e.target.value }))
                }
              >
                <option value="admin">Admin</option>
                <option value="read_only">Read-only</option>
              </select>
              <button
                type="button"
                className="btn btn-small btn-danger"
                onClick={() => act(() => api.del(`role-assignments/${a.id}`))}
                aria-label={`Remove access at ${a.office.name}`}
              >
                Remove
              </button>
            </span>
          </li>
        ))}
      </ul>
      <form
        className="stack"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          act(async () => {
            await api.post('role-assignments', { user_id: user.id, office_id: officeId, level });
            setOfficeId('');
          });
        }}
      >
        <OfficeSelect
          offices={offices}
          value={officeId}
          onChange={setOfficeId}
          label="Give access at"
        />
        <label>
          Level
          <select value={level} onChange={(e) => setLevel(e.target.value as 'admin' | 'read_only')}>
            <option value="read_only">Read-only — can view and export</option>
            <option value="admin">Admin — can enter and change data</option>
          </select>
        </label>
        <button type="submit" className="btn" disabled={!officeId}>
          Add access
        </button>
      </form>
      <h3>Effective scope</h3>
      {scope.data && scope.data.length === 0 && (
        <p className="muted small">Cannot see any office.</p>
      )}
      <ul className="plain-list scope-list">
        {scope.data?.map((o) => (
          <li key={o.id} style={{ paddingLeft: `${o.depth * 0.9}rem` }}>
            <span className="code">{o.code}</span> {o.name}{' '}
            <span className="muted small">{o.can_edit ? 'can edit' : 'view only'}</span>
          </li>
        ))}
      </ul>
      <h3>Account</h3>
      <div className="stack">
        <button
          type="button"
          className="btn"
          onClick={() => {
            if (
              !window.confirm(
                `Reset the password of ${user.email}? Their current password stops working at once.`,
              )
            )
              return;
            act(async () => {
              const res = await api.post<{ temporary_password: string }>(
                `users/${user.id}/reset-password`,
              );
              onSecret(res.temporary_password);
            });
          }}
        >
          Reset password
        </button>
        {!isSelf && (
          <button
            type="button"
            className={user.is_active ? 'btn btn-danger' : 'btn'}
            onClick={() => {
              const msg = user.is_active
                ? `Deactivate ${user.email}? They will not be able to sign in. Their past entries are kept.`
                : `Reactivate ${user.email}? They will be able to sign in again.`;
              if (window.confirm(msg))
                act(() => api.patch(`users/${user.id}`, { is_active: !user.is_active }));
            }}
          >
            {user.is_active ? 'Deactivate' : 'Reactivate'}
          </button>
        )}
      </div>
    </aside>
  );
}

function CreateUserDialog({
  offices,
  onClose,
  onCreated,
}: {
  offices: OfficeRow[];
  onClose: () => void;
  onCreated: (u: UserRow) => void;
}) {
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [officeId, setOfficeId] = useState('');
  const [level, setLevel] = useState<'admin' | 'read_only'>('read_only');
  const [error, setError] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault();
    try {
      const u = await api.post<UserRow>('users', {
        email,
        full_name: fullName,
        assignments: officeId ? [{ office_id: officeId, level }] : [],
      });
      onCreated(u);
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <Modal title="Add user" onClose={onClose}>
      <form className="stack" onSubmit={submit}>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Full name
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </label>
        <OfficeSelect
          offices={offices}
          value={officeId}
          onChange={setOfficeId}
          label="Access at office (optional)"
        />
        <label>
          Level
          <select value={level} onChange={(e) => setLevel(e.target.value as 'admin' | 'read_only')}>
            <option value="read_only">Read-only — can view and export</option>
            <option value="admin">Admin — can enter and change data</option>
          </select>
        </label>
        <p className="muted small">A temporary password is created and shown once.</p>
        <FormError message={error} />
        <div className="row">
          <button type="submit" className="btn btn-primary" disabled={!email}>
            Add user
          </button>
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
