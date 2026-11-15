import { useEffect, useState, useSyncExternalStore } from 'react';
import { requestsInFlight, subscribeInFlight } from '../api/client';

const SHOW_AFTER_MS = 300; // quick answers do not flash a bar

/** A thin "Loading…" bar under the navigation while the page waits for the server (P12.4). */
export default function LoadingBar() {
  const busy = useSyncExternalStore(subscribeInFlight, () => requestsInFlight() > 0);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(busy), busy ? SHOW_AFTER_MS : 0);
    return () => window.clearTimeout(timer);
  }, [busy]);
  return (
    <div className={`loading-bar ${visible ? 'is-visible' : ''}`} role="status" aria-live="polite">
      {visible ? 'Loading…' : ''}
    </div>
  );
}
