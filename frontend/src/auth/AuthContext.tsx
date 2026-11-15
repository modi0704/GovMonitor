import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError, SESSION_EXPIRED_EVENT, api } from '../api/client';
import type { Me } from '../api/types';
import { setDisplayTimeZone } from '../lib/format';

import { AuthContext, type AuthState } from './context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await api.get<Me>('me');
      setDisplayTimeZone(data.agency?.timezone);
      setMe(data);
      return data;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setMe(null);
        return null;
      }
      throw err;
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await api.get('auth/csrf');
        await refresh();
      } catch {
        // Server unreachable: the sign-in page will show the error on submit.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  useEffect(() => {
    function onExpired() {
      setMe((current) => {
        if (current) setSessionExpired(true);
        return null;
      });
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired);
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post('auth/logout');
    } finally {
      setMe(null);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      me,
      loading,
      sessionExpired,
      setMe,
      refresh,
      signOut,
      clearExpired: () => setSessionExpired(false),
    }),
    [me, loading, sessionExpired, refresh, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
