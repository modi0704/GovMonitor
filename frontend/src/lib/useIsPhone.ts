import { useSyncExternalStore } from 'react';

/** Phones: the width below which editing screens are not offered (D12, P12.3). */
export const PHONE_QUERY = '(max-width: 600px)';

function subscribe(onChange: () => void) {
  if (typeof window === 'undefined' || !window.matchMedia) return () => {};
  const mql = window.matchMedia(PHONE_QUERY);
  mql.addEventListener('change', onChange);
  return () => mql.removeEventListener('change', onChange);
}

function snapshot(): boolean {
  return (
    typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia(PHONE_QUERY).matches
  );
}

export function useIsPhone(): boolean {
  return useSyncExternalStore(subscribe, snapshot, () => false);
}
