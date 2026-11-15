import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, api } from '../api/client';
import type { Me } from '../api/types';
import AuthCard from '../components/AuthCard';
import FormError from '../components/FormError';
import { useAuth } from '../auth/useAuth';

export const PASSWORD_RULES = 'At least 12 characters, not only digits, not a common password.';

export default function ChangePasswordPage() {
  const { me, setMe } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const forced = me?.must_change_password ?? false;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (next.length < 12) return setError('The new password must have at least 12 characters.');
    if (next !== confirm) return setError('The two new passwords do not match.');
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ status: 'ok'; me: Me }>('auth/password', {
        current_password: current,
        new_password: next,
      });
      setMe(res.me);
      navigate('/', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        const fields = err.fieldErrors;
        setError(fields.new_password?.join(' ') ?? err.message);
      } else {
        setError('Could not change the password.');
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title={forced ? 'Choose a new password' : 'Change password'}
      subtitle={
        forced
          ? 'Your administrator set a temporary password. Choose your own to continue.'
          : undefined
      }
      onSubmit={onSubmit}
    >
      <label>
        {forced ? 'Temporary password' : 'Current password'}
        <input
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
          required
        />
      </label>
      <label>
        New password
        <input
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
          aria-describedby="pw-rules"
          required
        />
      </label>
      <p id="pw-rules" className="muted small">
        {PASSWORD_RULES}
      </p>
      <label>
        Repeat the new password
        <input
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
        />
      </label>
      <FormError message={error} />
      <button type="submit" className="btn btn-primary" disabled={busy}>
        {busy ? 'Saving…' : 'Save password'}
      </button>
      {!forced && (
        <button type="button" className="btn btn-link" onClick={() => navigate(-1)}>
          Cancel
        </button>
      )}
    </AuthCard>
  );
}
