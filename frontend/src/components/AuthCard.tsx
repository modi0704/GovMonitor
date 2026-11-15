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
      <form className="auth-card" onSubmit={onSubmit} aria-labelledby="auth-title" noValidate>
        <div className="brand">
          <img src="/favicon.svg" alt="" width={32} height={32} />
          <span>GovMonitor</span>
        </div>
        <h1 id="auth-title">{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
        {children}
      </form>
    </main>
  );
}
