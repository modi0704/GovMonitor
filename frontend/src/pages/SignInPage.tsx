import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { ApiError, api } from '../api/client';
import type { LoginResponse, Me } from '../api/types';
import AuthCard from '../components/AuthCard';
import FormError from '../components/FormError';
import { useAuth } from '../auth/useAuth';

function safeNext(next: string | null): string {
  // Only same-app paths: never redirect to another site after sign-in.
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/';
}

export default function SignInPage() {
  const { me, setMe, sessionExpired, clearExpired } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [step, setStep] = useState<'password' | 'code'>('password');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [useRecovery, setUseRecovery] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const next = safeNext(params.get('next'));

  if (me && !busy)
    return <Navigate to={me.must_change_password ? '/change-password' : next} replace />;

  function finish(user: Me) {
    clearExpired();
    setMe(user);
    navigate(user.must_change_password ? '/change-password' : next, { replace: true });
  }

  async function submitPassword(e: FormEvent) {
    e.preventDefault();
    if (!email || !password) {
      setError('Enter your email and password.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<LoginResponse>(
        'auth/login',
        { email, password },
        { quietAuth: true },
      );
      if (res.status === '2fa_required') {
        setStep('code');
        setPassword('');
      } else {
        finish(res.me);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.');
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = useRecovery ? { recovery_code: code } : { code };
      const res = await api.post<{ status: 'ok'; me: Me }>('auth/2fa', body, { quietAuth: true });
      finish(res.me);
    } catch (err) {
      if (err instanceof ApiError && (err.body as { code?: string })?.code === '2fa_expired') {
        setStep('password');
      }
      setError(err instanceof ApiError ? err.message : 'Verification failed.');
    } finally {
      setBusy(false);
    }
  }

  if (step === 'code') {
    return (
      <AuthCard
        title="Two-step verification"
        subtitle={
          useRecovery
            ? 'Enter one of your recovery codes. Each code works once.'
            : 'Enter the 6-digit code from your authenticator app.'
        }
        onSubmit={submitCode}
      >
        <label>
          {useRecovery ? 'Recovery code' : 'Code'}
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            inputMode={useRecovery ? 'text' : 'numeric'}
            autoComplete="one-time-code"
            autoFocus
            maxLength={useRecovery ? 20 : 6}
          />
        </label>
        <FormError message={error} />
        <button type="submit" className="btn btn-primary" disabled={busy || !code}>
          {busy ? 'Checking…' : 'Verify'}
        </button>
        <button
          type="button"
          className="btn btn-link"
          onClick={() => {
            setUseRecovery(!useRecovery);
            setCode('');
            setError(null);
          }}
        >
          {useRecovery ? 'Use a code from my app instead' : 'I lost my phone — use a recovery code'}
        </button>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Sign in" onSubmit={submitPassword}>
      {(sessionExpired || params.get('expired')) && (
        <p className="form-message" role="status">
          Your session ended because it was idle. Please sign in again.
        </p>
      )}
      <label>
        Email
        <input
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoFocus
          required
        />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      <FormError message={error} />
      <button type="submit" className="btn btn-primary" disabled={busy}>
        {busy ? 'Signing in…' : 'Sign in'}
      </button>
      <Link to="/forgot-password" className="small-link">
        Forgot your password?
      </Link>
    </AuthCard>
  );
}
