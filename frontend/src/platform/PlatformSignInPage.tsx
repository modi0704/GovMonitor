import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, api } from '../api/client';
import AuthCard from '../components/AuthCard';
import FormError from '../components/FormError';
import { platformApi } from './platformApi';

export default function PlatformSignInPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [needCode, setNeedCode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.get('auth/csrf');
      await platformApi.post('auth/login', { email, password, code });
      navigate('/platform', { replace: true });
    } catch (err) {
      if (err instanceof ApiError && (err.body as { code?: string })?.code === '2fa_required') {
        setNeedCode(true);
        return;
      }
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.');
    }
  }

  return (
    <AuthCard title="Platform owner sign-in" subtitle="For vendor staff only." onSubmit={onSubmit}>
      <label>
        Email
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label>
        Password
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
      {needCode && (
        <label>
          Code from your authenticator app
          <input
            inputMode="numeric"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </label>
      )}
      <FormError message={error} />
      <button type="submit" className="btn btn-primary">
        Sign in
      </button>
    </AuthCard>
  );
}
