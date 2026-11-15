import { useAuth } from '../auth/useAuth';

export default function HomePage() {
  const { me } = useAuth();
  return (
    <section className="page">
      <h1>Welcome{me?.full_name ? `, ${me.full_name}` : ''}</h1>
      <p className="muted">
        {me?.agency.name}. Dashboards, plans and monthly reports appear here as they are set up.
      </p>
      {me && me.roles.length === 0 && (
        <p className="notice">
          You are not assigned to any office yet. Ask your agency administrator to give you access.
        </p>
      )}
    </section>
  );
}
