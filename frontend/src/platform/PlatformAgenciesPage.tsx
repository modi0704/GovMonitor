import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import type { PlatformAgency } from '../api/types';
import FormError from '../components/FormError';
import { platformApi } from './platformApi';

const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

export default function PlatformAgenciesPage() {
  const navigate = useNavigate();
  const [agencies, setAgencies] = useState<PlatformAgency[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: '',
    code: '',
    fiscal_year_start_month: 1,
    root_level_name: 'Agency',
  });
  const [adminFor, setAdminFor] = useState<PlatformAgency | null>(null);
  const [adminEmail, setAdminEmail] = useState('');
  const [adminName, setAdminName] = useState('');
  const [created, setCreated] = useState<{ email: string; temporary_password: string } | null>(
    null,
  );

  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let active = true;
    platformApi
      .get<PlatformAgency[]>('agencies')
      .then((data) => {
        if (active) setAgencies(data);
      })
      .catch((err: unknown) => {
        if (!active) return;
        if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
          navigate('/platform/sign-in', { replace: true });
        } else if (err instanceof ApiError && err.status === 404) {
          setError('The platform area is not available in a single-agency installation.');
        } else {
          setError(err instanceof ApiError ? err.message : 'Could not load agencies.');
        }
      });
    return () => {
      active = false;
    };
  }, [navigate, reloadKey]);

  async function createAgency(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await platformApi.post('agencies', form);
      setForm({ name: '', code: '', fiscal_year_start_month: 1, root_level_name: 'Agency' });
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the agency.');
    }
  }

  async function toggle(a: PlatformAgency) {
    const next = a.status === 'active' ? 'suspended' : 'active';
    const verb = next === 'suspended' ? 'Suspend' : 'Reactivate';
    const consequence =
      next === 'suspended'
        ? 'All its users will be signed out and unable to sign in. Their data is kept.'
        : 'Its users will be able to sign in again.';
    if (!window.confirm(`${verb} ${a.name}? ${consequence}`)) return;
    await platformApi.patch(`agencies/${a.id}`, { status: next });
    load();
  }

  async function createAdmin(e: FormEvent) {
    e.preventDefault();
    if (!adminFor) return;
    setError(null);
    try {
      const res = await platformApi.post<{ email: string; temporary_password: string }>(
        `agencies/${adminFor.id}/admins`,
        { email: adminEmail, full_name: adminName },
      );
      setCreated(res);
      setAdminFor(null);
      setAdminEmail('');
      setAdminName('');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the administrator.');
    }
  }

  async function signOut() {
    await platformApi.post('auth/logout').catch(() => undefined);
    navigate('/platform/sign-in', { replace: true });
  }

  return (
    <main className="page page-wide">
      <div className="page-header">
        <h1>Agencies</h1>
        <button type="button" className="btn" onClick={signOut}>
          Sign out
        </button>
      </div>
      <FormError message={error} />
      {created && (
        <div className="notice" role="status">
          Administrator <strong>{created.email}</strong> created. Temporary password (shown once):{' '}
          <code>{created.temporary_password}</code>. They must change it at first sign-in.
        </div>
      )}
      {agencies === null && !error && <p>Loading…</p>}
      {agencies && agencies.length === 0 && (
        <p className="muted">No agencies yet. Create the first one below.</p>
      )}
      {agencies && agencies.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Agency</th>
              <th>Code</th>
              <th>Fiscal year starts</th>
              <th>Status</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {agencies.map((a) => (
              <tr key={a.id}>
                <td>{a.name}</td>
                <td>{a.code}</td>
                <td>{MONTHS[a.fiscal_year_start_month - 1]}</td>
                <td>
                  <span className={`chip chip-${a.status}`}>{a.status}</span>
                </td>
                <td className="actions">
                  <button type="button" className="btn btn-small" onClick={() => setAdminFor(a)}>
                    Add administrator
                  </button>
                  <button type="button" className="btn btn-small" onClick={() => toggle(a)}>
                    {a.status === 'active' ? 'Suspend' : 'Reactivate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {adminFor && (
        <form className="card stack" onSubmit={createAdmin}>
          <h2>New administrator for {adminFor.name}</h2>
          <label>
            Email
            <input
              type="email"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
            />
          </label>
          <label>
            Full name
            <input value={adminName} onChange={(e) => setAdminName(e.target.value)} />
          </label>
          <div className="row">
            <button type="submit" className="btn btn-primary" disabled={!adminEmail}>
              Create administrator
            </button>
            <button type="button" className="btn" onClick={() => setAdminFor(null)}>
              Cancel
            </button>
          </div>
        </form>
      )}
      <form className="card stack" onSubmit={createAgency}>
        <h2>New agency</h2>
        <label>
          Name
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <label>
          Code (letters, digits, hyphens)
          <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
        </label>
        <label>
          Fiscal year starts in
          <select
            value={form.fiscal_year_start_month}
            onChange={(e) => setForm({ ...form, fiscal_year_start_month: Number(e.target.value) })}
          >
            {MONTHS.map((m, i) => (
              <option key={m} value={i + 1}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label>
          Name of the top level (e.g. Ministry, Department)
          <input
            value={form.root_level_name}
            onChange={(e) => setForm({ ...form, root_level_name: e.target.value })}
          />
        </label>
        <button type="submit" className="btn btn-primary" disabled={!form.name || !form.code}>
          Create agency
        </button>
      </form>
    </main>
  );
}
