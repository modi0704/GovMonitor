import type { FormEvent, ReactNode } from 'react';

export default function AuthCard({
  title,
  onSubmit,
  children,
  subtitle,
}: {
  title: string;
  subtitle?: string;
  onSubmit: (e: FormEvent) => void;
  children: ReactNode;
}) {
  return (
    <main className="auth-shell">
      <aside className="auth-intro" aria-label="About GovMonitor">
        <div className="brand brand-inverse">
          <img src="/favicon.svg" alt="" width={36} height={36} />
          <span>GovMonitor</span>
        </div>
        <div className="auth-intro-copy">
          <p className="eyebrow">GOVERNMENT PERFORMANCE MONITORING</p>
          <h2>
            A clear view of
            <br />
            every office's progress.
          </h2>
          <p>
            Bring yearly plans, monthly accomplishments, and reviewed results into one shared
            workspace.
          </p>
          <ol className="auth-steps">
            <li>
              <span>01</span>
              <div>
                <strong>Plan with purpose</strong>
                <p>Set activities and monthly targets.</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Report with confidence</strong>
                <p>Record completed work and supporting files.</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Review the whole picture</strong>
                <p>Follow progress and share final results.</p>
              </div>
            </li>
          </ol>
        </div>
        <p className="auth-intro-footer">Account access is managed by your agency administrator.</p>
      </aside>
      <div className="auth-form-wrap">
        <form className="auth-card" onSubmit={onSubmit} aria-labelledby="auth-title" noValidate>
          <div className="brand">
            <img src="/favicon.svg" alt="" width={32} height={32} />
            <span>GovMonitor</span>
          </div>
          <h1 id="auth-title">{title}</h1>
          {subtitle && <p className="muted">{subtitle}</p>}
          {!subtitle && title === 'Sign in' && (
            <p className="muted">Welcome back. Enter your agency account details to continue.</p>
          )}
          {children}
        </form>
        <p className="auth-support">Need an account? Contact your agency administrator.</p>
      </div>
    </main>
  );
}
