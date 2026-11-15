import { lazy, Suspense } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';

const DashboardPage = lazy(() => import('./dashboard/DashboardPage'));

/** Start page: setup reminders, then the dashboard of the user's top office (P8.2). */
export default function HomePage() {
  const { me } = useAuth();
  const setupNotice = me?.is_agency_admin && !me.agency.setup_complete && (
    <div className="page notice">
      <strong>Your agency is not set up yet.</strong> Name your levels, build your office structure
      and add the first users. <Link to="/setup">Start the setup</Link>
    </div>
  );
  if (me && me.roles.length > 0) {
    return (
      <>
        {setupNotice}
        <Suspense fallback={<div className="page-loading">Loading…</div>}>
          <DashboardPage />
        </Suspense>
      </>
    );
  }
  return (
    <section className="page">
      <h1>Welcome{me?.full_name ? `, ${me.full_name}` : ''}</h1>
      <p className="muted">{me?.agency.name}</p>
      {setupNotice}
      {me && me.roles.length === 0 && (
        <p className="notice">
          You are not assigned to any office yet. Ask your agency administrator to give you access.
        </p>
      )}
    </section>
  );
}
