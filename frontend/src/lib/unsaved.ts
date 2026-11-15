import { useEffect } from 'react';

/** Unsaved-changes guard (P12.4): screens with edits register here; leaving through any link in
 * the app (or closing the tab) asks first. */
const dirty = new Map<string, string>();

export const LEAVE_MESSAGE = 'You have unsaved changes. Leave this page and lose them?';

export function hasUnsavedChanges(): boolean {
  return dirty.size > 0;
}

/** Ask before leaving; true when there is nothing unsaved or the user agrees to lose it. */
export function confirmLeave(): boolean {
  if (!hasUnsavedChanges()) return true;
  const ok = window.confirm(LEAVE_MESSAGE);
  if (ok) dirty.clear();
  return ok;
}

export function useUnsavedChanges(key: string, isDirty: boolean) {
  useEffect(() => {
    if (!isDirty) {
      dirty.delete(key);
      return;
    }
    dirty.set(key, LEAVE_MESSAGE);
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => {
      dirty.delete(key);
      window.removeEventListener('beforeunload', onBeforeUnload);
    };
  }, [key, isDirty]);
}

/** Capture clicks on in-app links before the router sees them (installed once by the shell). */
export function useLeaveGuard() {
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!hasUnsavedChanges() || e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; // new tab: nothing is lost
      const link = (e.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
      if (!link || link.target === '_blank' || link.hasAttribute('download')) return;
      if (link.origin !== window.location.origin) return;
      if (link.pathname === window.location.pathname && link.search === window.location.search)
        return;
      if (!confirmLeave()) {
        e.preventDefault();
        e.stopPropagation();
      }
    }
    document.addEventListener('click', onClick, true);
    return () => document.removeEventListener('click', onClick, true);
  }, []);
}
