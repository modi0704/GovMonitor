import { useState, type FormEvent } from 'react';

/** Placeholder sign-in page (P0.4). The working sign-in flow arrives in P1.10. */
export default function SignInPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState<string | null>(null);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setMessage('Sign-in is not available yet.');
  }

  return (
    <main className="auth-shell">
      <form className="auth-card" onSubmit={onSubmit} aria-labelledby="signin-title">
        <div className="brand">
          <img src="/favicon.svg" alt="" width={32} height={32} />
          <span>GovMonitor</span>
        </div>
        <h1 id="signin-title">Sign in</h1>
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
        {message && (
          <p className="form-message" role="status">
            {message}
          </p>
        )}
        <button type="submit" className="btn btn-primary">
          Sign in
        </button>
      </form>
    </main>
  );
}
