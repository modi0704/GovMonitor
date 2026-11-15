import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { ApiError, api } from '../api/client';
import { errorMessage } from '../api/useResource';
import FormError from '../components/FormError';
import { useAuth } from '../auth/useAuth';

interface Setup {
  secret: string;
  otpauth_uri: string;
  qr_svg: string;
}

/** Account security: two-step verification (TOTP) on/off, recovery codes, password link. */
export default function SecurityPage() {
  const { me, refresh } = useAuth();
  const [setup, setSetup] = useState<Setup | null>(null);
  const [code, setCode] = useState('');
  const [codes, setCodes] = useState<string[] | null>(null);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  async function start() {
    setError(null);
    try {
      setSetup(await api.post<Setup>('auth/2fa/setup'));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start the setup.');
    }
  }

  async function enable(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.post<{ recovery_codes: string[] }>('auth/2fa/enable', { code });
      setCodes(res.recovery_codes);
      setSetup(null);
      setCode('');
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not turn it on.');
    }
  }

  async function disable(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.post('auth/2fa/disable', { password });
      setPassword('');
      setCodes(null);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not turn it off.');
    }
  }

  return (
    <section className="page">
      <h1>Sign-in security</h1>
      <div className="card">
        <h2>Password</h2>
        <p>
          <Link to="/change-password">Change your password</Link>
        </p>
      </div>
      <div className="card">
        <h2>Two-step verification</h2>
        <p className="muted">
          When it is on, signing in also needs a 6-digit code from an authenticator app on your
          phone.
        </p>
        <FormError message={error} />
        {codes && (
          <div className="notice" role="status">
            <p>
              <strong>Save these recovery codes now.</strong> Each one lets you sign in once if you
              lose your phone. They will not be shown again.
            </p>
            <ul className="code-list">
              {codes.map((c) => (
                <li key={c}>
                  <code>{c}</code>
                </li>
              ))}
            </ul>
          </div>
        )}
        {me?.has_2fa ? (
          <form onSubmit={disable} className="stack">
            <p>
              Status: <strong>on</strong>
            </p>
            <label>
              Your password, to turn it off
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <button type="submit" className="btn" disabled={!password}>
              Turn off two-step verification
            </button>
          </form>
        ) : setup ? (
          <form onSubmit={enable} className="stack">
            <p>1. Scan this code with your authenticator app.</p>
            <div className="qr" dangerouslySetInnerHTML={{ __html: setup.qr_svg }} />
            <p className="muted small">
              Cannot scan? Enter this key: <code>{setup.secret}</code>
            </p>
            <label>
              2. Enter the 6-digit code the app shows
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
            <button type="submit" className="btn btn-primary" disabled={code.length !== 6}>
              Turn on
            </button>
          </form>
        ) : (
          <button type="button" className="btn btn-primary" onClick={start}>
            Set up two-step verification
          </button>
        )}
      </div>
      <EmailAlerts />
    </section>
  );
}

/** Personal opt-out from alert emails (P11.4); in-app notifications are not affected. */
function EmailAlerts() {
  const { me, refresh } = useAuth();
  const [error, setError] = useState<string | null>(null);
  if (!me) return null;
  async function toggle(optOut: boolean) {
    setError(null);
    try {
      await api.patch('me', { email_opt_out: optOut });
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    }
  }
  return (
    <div className="card">
      <h2>Email alerts</h2>
      <label className="check">
        <input
          type="checkbox"
          checked={!me.email_opt_out}
          onChange={(e) => toggle(!e.target.checked)}
        />
        Send me a daily email of my new notifications (when your agency has email turned on)
      </label>
      <FormError message={error} />
    </div>
  );
}
