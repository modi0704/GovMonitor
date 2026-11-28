import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import type { Level, OfficeRow } from '../api/types';
import { errorMessage } from '../api/useResource';
import FormError from '../components/FormError';
import { useAuth } from '../auth/useAuth';
import { parseOfficeList } from './structure/parseOfficeList';

const STEPS = ['Level names', 'Top office', 'Offices'] as const;

/** First-run setup (P2.7): level names → top office → offices. One officer enters everything, so
 * there is no step for other users (D49). */
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
  const [importErrors, setImportErrors] = useState<{ row: number; message: string }[]>([]);

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
            <h2>How are your offices organized?</h2>
            <p className="muted">
              Start with the highest office, for example Ministry, then Service, then Division. You
              can add more levels later.
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
              it beneath the one above. You can also leave it empty and add offices later on the
              Offices page.
            </p>
            <textarea
              rows={10}
              className="mono"
              value={officeText}
              aria-label="Offices"
              onChange={(e) => setOfficeText(e.target.value)}
              placeholder="Enter your office codes and names, one office per line."
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
                {officeText.trim() ? 'Add offices and finish' : 'Finish setup'}
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
