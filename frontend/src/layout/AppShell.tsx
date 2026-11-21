import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/useAuth';
import { useLeaveGuard } from '../lib/unsaved';
import { useFocusableScrollRegions } from './useFocusableScrollRegions';
import LoadingBar from './LoadingBar';
import NotificationBell from './NotificationBell';
import GuideBar from './GuideBar';
import { NAV_GROUPS, NAV_ITEMS } from './nav';
import NavIcon from './NavIcon';

const mainElement = () => document.querySelector<HTMLElement>('main.content');

export default function AppShell() {
  const { me, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!menuOpen) return;
    sidebarRef.current?.querySelector<HTMLElement>('.mainnav a')?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setMenuOpen(false);
        menuRef.current?.focus();
      }
    }
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [menuOpen]);
  const visible = NAV_ITEMS.filter((item) => me && item.show(me));
  const activePage =
    [...visible]
      .sort((a, b) => b.to.length - a.to.length)
      .find((item) => item.to !== '/' && location.pathname.startsWith(item.to))?.label ??
    (location.pathname === '/account/security'
      ? 'Account security'
      : location.pathname === '/setup'
        ? 'Agency setup'
        : (visible.find((item) => item.to === '/')?.label ?? 'Dashboard'));
  const role = me?.is_agency_admin
    ? 'Agency administrator'
    : me?.roles.some((r) => r.level === 'admin')
      ? 'Office administrator'
      : 'Read-only user';
  const accountName = me?.full_name || me?.email || 'Account';
  const initials = accountName
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join('')
    .toUpperCase();
  function closeMenu() {
    setMenuOpen(false);
    if (menuOpen) requestAnimationFrame(() => mainElement()?.focus());
  }
  useLeaveGuard();
  useFocusableScrollRegions(mainElement);
  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside
        ref={sidebarRef}
        className={`sidebar ${menuOpen ? 'is-open' : ''}`}
        id="workspace-navigation"
        aria-label="Workspace"
      >
        <NavLink to="/" className="brand brand-inverse">
          <img src="/favicon.svg" alt="" width={32} height={32} />
          <span>GovMonitor</span>
        </NavLink>
        <p className="sidebar-caption">AGENCY WORKSPACE</p>
        <nav className="mainnav" aria-label="Main">
          {NAV_GROUPS.map((group) => {
            const items = group.labels.flatMap((label) =>
              visible.filter((item) => item.label === label),
            );
            if (items.length === 0) return null;
            const links = items.map((item) => (
              <NavLink
                key={`${item.to}-${item.label}`}
                to={item.to}
                end={item.to === '/'}
                onClick={closeMenu}
                className={({ isActive }) =>
                  [item.desktopOnly ? 'desktop-only' : '', isActive ? 'active' : '']
                    .filter(Boolean)
                    .join(' ')
                }
              >
                <NavIcon name={item.icon} />
                <span>{item.label}</span>
              </NavLink>
            ));
            if (group.folded) {
              const holdsActive = items.some((item) => item.label === activePage);
              return (
                <details
                  className="nav-group nav-fold"
                  key={group.title}
                  open={holdsActive || undefined}
                >
                  <summary className="nav-group-title">{group.title}</summary>
                  {links}
                </details>
              );
            }
            return (
              <div className="nav-group" key={group.title}>
                <p className="nav-group-title">{group.title}</p>
                {links}
              </div>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <span className="workspace-dot" />
          {me?.agency.name}
          <p>{role}</p>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="topbar">
          <button
            ref={menuRef}
            type="button"
            className="btn mobile-menu"
            aria-expanded={menuOpen}
            aria-controls="workspace-navigation"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? 'Close menu' : 'Menu'}
          </button>
          <div className="workspace-heading">
            <span className="agency-name">{me?.agency.name}</span>
            <span className="workspace-page">{activePage}</span>
          </div>
          <nav className="topnav" aria-label="Account">
            <NotificationBell />
            <NavLink to="/account/security" className="account-link">
              <span className="account-avatar" aria-hidden="true">
                {initials}
              </span>
              <span className="account-copy">
                <strong>{accountName}</strong>
                <span>{role}</span>
              </span>
            </NavLink>
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
          {me?.is_agency_admin && <GuideBar />}
          <Outlet />
        </main>
        <footer className="workspace-footer">
          GovMonitor<span>Plan. Report. Review.</span>
        </footer>
      </div>
    </div>
  );
}
