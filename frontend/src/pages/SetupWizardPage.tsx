import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Level, OfficeRow, UserRow } from '../api/types';
import { errorMessage } from '../api/useResource';
import FormError from '../components/FormError';
import { useAuth } from '../auth/useAuth';
import { parseOfficeList } from './structure/parseOfficeList';

const STEPS = ['Level names', 'Top office', 'Offices', 'First users'] as const;

/** First-run setup (P2.7): level names → top office → offices → first users. */
export default function SetupWizardPage() {
  const { me, refresh } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [levels, setLevels] = useState<string[]>(['', '', '']);
  const [root, setRoot] = useState<OfficeRow | null>(null);
  const [rootName, setRootName] = useState('');
  const [rootCode, setRootCode] = useState('');
  const [officeText, setOfficeText] = useState('');
  const [offices, setOffices] = useState<OfficeRow[]>([]);
  const [importErrors, setImportErrors] = useState<{ row: number; message: string }[]>([]);
  const [newUser, setNewUser] = useState({
    email: '',
    full_name: '',
    office_id: '',
    level: 'admin',
  });
  const [created, setCreated] = useState<{ email: string; password: string }[]>([]);

  useEffect(() => {
    let active = true;
    Promise.all([api.get<Level[]>('levels'), api.get<OfficeRow[]>('offices')])
      .then(([lv, of]) => {
        if (!active) return;
        if (lv.length) setLevels(lv.map((l) => l.name).concat(lv.length < 2 ? [''] : []));
        const top = of.find((o) => o.parent_id === null) ?? null;
        setRoot(top);
        setRootName(top?.name ?? '');
        setRootCode(top?.code ?? '');
        setOffices(of);
      })
      .catch((err: unknown) => active && setError(errorMessage(err)));
    return () => {
      active = false;
    };
  }, []);

  if (me && !me.is_agency_admin) {
    return (
      <section className="page">
        <p className="notice">Only the agency administrator can run the setup.</p>
      </section>
    );
  }

  async function run(fn: () => Promise<void>) {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  const saveLevels = () =>
    run(async () => {
      const names = levels.map((l) => l.trim()).filter(Boolean);
      if (!names.length) throw new Error();
      await api.put('levels', { names });
      setStep(1);
    });

  const saveRoot = () =>
    run(async () => {
      if (!root) return;
      const updated = await api.patch<OfficeRow>(`offices/${root.id}`, {
        name: rootName,
        code: rootCode,
      });
      setRoot(updated);
      await api.patch('agency', { name: rootName });
      setStep(2);
    });

  const saveOffices = () =>
    run(async () => {
      if (!root) return;
      if (officeText.trim()) {
        const rows = parseOfficeList(officeText);
        const preview = await api.post<{ errors: { row: number; message: string }[] }>(
          'offices/import',
          {
            parent_id: root.id,
            rows,
            dry_run: true,
          },
        );
        setImportErrors(preview.errors);
        if (preview.errors.length) return;
        await api.post('offices/import', { parent_id: root.id, rows });
        setOfficeText('');
      }
      setOffices(await api.get<OfficeRow[]>('offices'));
      setStep(3);
    });

  const addUser = () =>
    run(async () => {
      const u = await api.post<UserRow>('users', {
        email: newUser.email,
        full_name: newUser.full_name,
        assignments: newUser.office_id
          ? [{ office_id: newUser.office_id, level: newUser.level }]
          : [],
      });
      setCreated([...created, { email: u.email, password: u.temporary_password ?? '' }]);
      setNewUser({ email: '', full_name: '', office_id: '', level: 'admin' });
    });

  const finish = () =>
    run(async () => {
      await api.patch('agency', { setup_complete: true });
      await refresh();
      navigate('/', { replace: true });
    });

  return (
    <section className="page">
      <h1>Set up your agency</h1>
      <ol className="stepper" aria-label="Setup steps">
        {STEPS.map((s, i) => (
          <li
            key={s}
            className={i === step ? 'current' : i < step ? 'done' : ''}
            aria-current={i === step ? 'step' : undefined}
          >
            <span className="step-num">{i + 1}</span> {s}
          </li>
        ))}
      </ol>
      <FormError message={error} />
      <div className="card stack">
        {step === 0 && (
          <>
            <h2>What are the levels of your structure called?</h2>
            <p className="muted">
              From the top down, for example Ministry → Service → Division. You can add more later.
            </p>
            {levels.map((name, i) => (
              <label key={i}>
                Level {i + 1}
                {i === 0 ? ' (the whole agency)' : ''}
                <input
                  value={name}
                  onChange={(e) => setLevels(levels.map((x, j) => (j === i ? e.target.value : x)))}
                />
              </label>
            ))}
            <div className="row">
              <button
                type="button"
                className="btn btn-link"
                onClick={() => setLevels([...levels, ''])}
              >
                Add a level
              </button>
            </div>
            <div className="row">
              <button
                type="button"
                className="btn btn-primary"
                onClick={saveLevels}
                disabled={!levels[0]?.trim()}
              >
                Next
              </button>
            </div>
          </>
        )}
        {step === 1 && (
          <>
            <h2>The top office</h2>
            <p className="muted">This is the agency itself. Reports and exports use this name.</p>
            <label>
              Name
              <input value={rootName} onChange={(e) => setRootName(e.target.value)} />
            </label>
            <label>
              Code
              <input
                value={rootCode}
                onChange={(e) => setRootCode(e.target.value)}
                maxLength={40}
              />
            </label>
            <div className="row">
              <button type="button" className="btn" onClick={() => setStep(0)}>
                Back
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={saveRoot}
                disabled={!rootName.trim() || !rootCode.trim()}
              >
                Next
              </button>
            </div>
          </>
        )}
        {step === 2 && (
          <>
            <h2>Offices</h2>
            <p className="muted">
              Paste your offices, one per line: code, a tab (or “ - ”), name. Indent a line to put
              it beneath the one above. You can also skip this and build the structure later on the
              Structure page.
            </p>
            <textarea
              rows={10}
              className="mono"
              value={officeText}
              aria-label="Offices"
              onChange={(e) => setOfficeText(e.target.value)}
              placeholder={
                'ODS\tOffice of the Director for Services\n\tPME\tPlanning and Monitoring'
              }
            />
            {importErrors.length > 0 && (
              <ul className="form-error">
                {importErrors.map((e, i) => (
                  <li key={i}>
                    Line {e.row}: {e.message}
                  </li>
                ))}
              </ul>
            )}
            <div className="row">
              <button type="button" className="btn" onClick={() => setStep(1)}>
                Back
              </button>
              <button type="button" className="btn btn-primary" onClick={saveOffices}>
                {officeText.trim() ? 'Add offices and continue' : 'Skip'}
              </button>
            </div>
          </>
        )}
        {step === 3 && (
          <>
            <h2>First users</h2>
            <p className="muted">
              Give each office at least one person who enters its data (Admin).
            </p>
            {created.length > 0 && (
              <div className="notice">
                <p>Temporary passwords (shown once — hand them over securely):</p>
                <ul className="plain-list">
                  {created.map((c) => (
                    <li key={c.email}>
                      {c.email}: <code>{c.password}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <label>
              Email
              <input
                type="email"
                value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
              />
            </label>
            <label>
              Full name
              <input
                value={newUser.full_name}
                onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
              />
            </label>
            <label>
              Office
              <select
                value={newUser.office_id}
                onChange={(e) => setNewUser({ ...newUser, office_id: e.target.value })}
              >
                <option value="">Choose an office…</option>
                {offices.map((o) => (
                  <option key={o.id} value={o.id}>
                    {'  '.repeat(o.depth)}
                    {o.code} {o.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Level
              <select
                value={newUser.level}
                onChange={(e) => setNewUser({ ...newUser, level: e.target.value })}
              >
                <option value="admin">Admin — enters and changes data</option>
                <option value="read_only">Read-only — views and exports</option>
              </select>
            </label>
            <div className="row">
              <button type="button" className="btn" onClick={addUser} disabled={!newUser.email}>
                Add user
              </button>
            </div>
            <div className="row">
              <button type="button" className="btn" onClick={() => setStep(2)}>
                Back
              </button>
              <button type="button" className="btn btn-primary" onClick={finish}>
                Finish setup
              </button>
            </div>
          </>
        )}
      </div>
      <p className="muted small">
        You can leave and come back: everything saved so far is kept.{' '}
        <Link to="/">Go to the start page</Link>
      </p>
    </section>
  );
}
