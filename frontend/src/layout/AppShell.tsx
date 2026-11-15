import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { useLeaveGuard } from '../lib/unsaved';
import { useFocusableScrollRegions } from './useFocusableScrollRegions';
import LoadingBar from './LoadingBar';
import NotificationBell from './NotificationBell';
import { NAV_ITEMS } from './nav';

const mainElement = () => document.querySelector<HTMLElement>('main.content');

export default function AppShell() {
  const { me, signOut } = useAuth();
  const navigate = useNavigate();
  useLeaveGuard();
  useFocusableScrollRegions(mainElement);
  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="topbar">
        <NavLink to="/" className="brand brand-inverse">
          <img src="/favicon.svg" alt="" width={24} height={24} />
          <span>GovMonitor</span>
        </NavLink>
        <span className="agency-name">{me?.agency.name}</span>
        <nav className="topnav" aria-label="Account">
          <NotificationBell />
          <NavLink to="/account/security">{me?.full_name || me?.email}</NavLink>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={async () => {
              await signOut();
              navigate('/sign-in', { replace: true });
            }}
          >
            Sign out
          </button>
        </nav>
      </header>
      <nav className="mainnav" aria-label="Main">
        {me &&
          NAV_ITEMS.filter((item) => item.show(me)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={item.desktopOnly ? 'desktop-only' : undefined}
            >
              {item.label}
            </NavLink>
          ))}
      </nav>
      {me?.licence?.message && (
        <div
          className={`licence-banner ${me.licence.read_only ? 'is-blocking' : ''}`}
          role={me.licence.read_only ? 'alert' : 'status'}
        >
          {me.licence.message}{' '}
          {me.licence.read_only
            ? 'You can still sign in, read everything and export it. Ask your administrator to install a valid licence.'
            : 'Ask your administrator to renew it.'}
        </div>
      )}
      <LoadingBar />
      <main className="content" id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
