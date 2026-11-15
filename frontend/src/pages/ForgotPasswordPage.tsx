import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import AuthCard from '../components/AuthCard';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    try {
      await api.post('auth/password-reset', { email }, { quietAuth: true });
    } finally {
      setSent(true);
    }
  }

  return (
    <AuthCard title="Reset your password" onSubmit={onSubmit}>
      {sent ? (
        <p role="status">
          If email is set up for your agency and the address is registered, a reset link is on its
          way. Otherwise ask your agency administrator to reset your password.
        </p>
      ) : (
        <>
          <label>
            Email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <button type="submit" className="btn btn-primary" disabled={!email}>
            Send reset link
          </button>
        </>
      )}
      <Link to="/sign-in" className="small-link">
        Back to sign-in
      </Link>
    </AuthCard>
  );
}
