import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { useResource } from '../../api/useResource';
import FormError from '../../components/FormError';
import { dateTime } from '../../lib/format';
import type { NotificationList } from './types';

/** All notifications of the signed-in user (P11.3). */
export default function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const list = useResource<NotificationList>(
    `notifications?limit=200${unreadOnly ? '&unread=1' : ''}`,
  );
  const { reload } = list;

  async function markRead(id: string) {
    await api.post(`notifications/${id}/read`).catch(() => undefined);
    reload();
  }

  async function readAll() {
    await api.post('notifications/read-all').catch(() => undefined);
    reload();
  }

  return (
    <section className="page">
      <div className="page-header">
        <h1>Notifications</h1>
        <div className="row">
          <label className="check">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => setUnreadOnly(e.target.checked)}
            />
            Unread only
          </label>
          {(list.data?.unread ?? 0) > 0 && (
            <button type="button" className="btn" onClick={readAll}>
              Mark all read
            </button>
          )}
        </div>
      </div>
      <FormError message={list.error} />
      {list.data && list.data.results.length === 0 && (
        <p className="notice">Nothing here. Reminders, late reports and delays will appear here.</p>
      )}
      <ul className="notification-list">
        {list.data?.results.map((n) => (
          <li key={n.id} className={n.read_at ? '' : 'unread'}>
            <div>
              <strong>{n.link ? <Link to={n.link}>{n.title}</Link> : n.title}</strong>
              {n.body && <p className="small">{n.body}</p>}
              <span className="muted small">{dateTime(n.created_at)}</span>
            </div>
            {!n.read_at && (
              <button type="button" className="btn btn-small" onClick={() => markRead(n.id)}>
                Mark read
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
