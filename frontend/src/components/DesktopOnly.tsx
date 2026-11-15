import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useIsPhone } from '../lib/useIsPhone';

/** Editing screens are for computers (D12): on a phone, say so plainly instead of a broken grid. */
export default function DesktopOnly({ what, children }: { what: string; children: ReactNode }) {
  const phone = useIsPhone();
  if (!phone) return <>{children}</>;
  return (
    <section className="page">
      <div className="card desktop-only-notice" role="status">
        <h1>Open on a computer to edit</h1>
        <p>
          {what} needs a larger screen. On a phone you can follow the <Link to="/">dashboard</Link>,
          the <Link to="/rankings">rankings</Link> and your{' '}
          <Link to="/notifications">notifications</Link>, and attach photos to an activity from its
          history on the dashboard.
        </p>
      </div>
    </section>
  );
}
