import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ApiError, api } from '../api/client';
import AuthCard from '../components/AuthCard';
import FormError from '../components/FormError';
import { PASSWORD_RULES } from './ChangePasswordPage';

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError('The two passwords do not match.');
    setError(null);
    try {
      await api.post(
        'auth/password-reset/confirm',
        {
          agency: params.get('a') ?? '',
          user: params.get('u') ?? '',
          token: params.get('t') ?? '',
          new_password: password,
        },
        { quietAuth: true },
      );
      setDone(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? (err.fieldErrors.new_password?.join(' ') ?? err.message)
          : 'Failed.',
      );
    }
  }

  if (done) {
    return (
      <AuthCard title="Password changed" onSubmit={(e) => e.preventDefault()}>
        <p role="status">You can now sign in with your new password.</p>
        <Link to="/sign-in" className="btn btn-primary">
          Sign in
        </Link>
      </AuthCard>
    );
  }
  return (
    <AuthCard title="Choose a new password" subtitle={PASSWORD_RULES} onSubmit={onSubmit}>
      <label>
        New password
        <input
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <label>
        Repeat the new password
        <input
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </label>
      <FormError message={error} />
      <button type="submit" className="btn btn-primary" disabled={password.length < 12}>
        Save password
      </button>
    </AuthCard>
  );
}
