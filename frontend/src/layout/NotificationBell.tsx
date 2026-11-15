import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { dateTime } from '../lib/format';
import type { NotificationItem, NotificationList } from '../pages/alerts/types';
import { UNREAD_POLL_MS } from '../pages/alerts/types';

/** Bell with the unread count; opens the latest notifications (P11.3). */
export default function NotificationBell() {
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const [tick, setTick] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let active = true;
    api
      .get<{ unread: number }>('notifications/unread-count')
      .then((d) => active && setUnread(d.unread))
      .catch(() => undefined);
    const timer = window.setInterval(refresh, UNREAD_POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [tick, refresh]);

  useEffect(() => {
    if (!open) return;
    let active = true;
    api
      .get<NotificationList>('notifications', { limit: '8' })
      .then((d) => {
        if (!active) return;
        setItems(d.results);
        setUnread(d.unread);
      })
      .catch(() => undefined);
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      active = false;
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, tick]);

  async function follow(n: NotificationItem) {
    setOpen(false);
    if (!n.read_at) {
      const d = await api.post<{ unread: number }>(`notifications/${n.id}/read`).catch(() => null);
      if (d) setUnread(d.unread);
    }
    if (n.link) navigate(n.link);
  }

  async function readAll() {
    await api.post('notifications/read-all').catch(() => undefined);
    refresh();
  }

  const label = unread ? `Notifications, ${unread} unread` : 'Notifications';
  return (
    <div className="bell" ref={ref}>
      <button
        type="button"
        className="btn btn-ghost bell-button"
        aria-label={label}
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen((o) => !o)}
      >
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path
            d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        {unread > 0 && <span className="bell-count">{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Notifications">
          <div className="bell-head">
            <strong>Notifications</strong>
            {unread > 0 && (
              <button type="button" className="btn btn-link btn-small" onClick={readAll}>
                Mark all read
              </button>
            )}
          </div>
          {items === null ? (
            <p className="muted small">Loading…</p>
          ) : items.length === 0 ? (
            <p className="muted small">Nothing yet.</p>
          ) : (
            <ul className="bell-list">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    className={`bell-item ${n.read_at ? '' : 'unread'}`}
                    onClick={() => follow(n)}
                  >
                    <span className="bell-title">{n.title}</span>
                    <span className="muted small">{dateTime(n.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Link className="small" to="/notifications" onClick={() => setOpen(false)}>
            See all notifications
          </Link>
        </div>
      )}
    </div>
  );
}
