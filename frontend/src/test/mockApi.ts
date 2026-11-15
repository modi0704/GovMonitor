import { vi } from 'vitest';

type Handler = (body: unknown) => { status?: number; body?: unknown };

/** Route-table fetch mock: keys are "METHOD /path". Records every call. */
// Answered for every page (the notification bell in the app shell); tests may override them.
const DEFAULT_ROUTES = {
  'GET /api/v1/notifications/unread-count': { body: { unread: 0 } },
  'GET /api/v1/notifications': { body: { results: [], unread: 0 } },
};

export function mockApi(given: Record<string, Handler | { status?: number; body?: unknown }>) {
  const routes: Record<string, Handler | { status?: number; body?: unknown }> = {
    ...DEFAULT_ROUTES,
    ...given,
  };
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fn = vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = (init.method ?? 'GET').toUpperCase();
    const path = url.split('?')[0]!;
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
    calls.push({ method, path, body });
    const route = routes[`${method} ${path}`];
    if (!route) return new Response(JSON.stringify({ detail: 'Please sign in.' }), { status: 401 });
    const res = typeof route === 'function' ? route(body) : route;
    return new Response(res.body === undefined ? '' : JSON.stringify(res.body), {
      status: res.status ?? 200,
    });
  });
  vi.stubGlobal('fetch', fn);
  return calls;
}

export const ME = {
  id: 'u1',
  email: 'ana@alpha.gov',
  full_name: 'Ana',
  must_change_password: false,
  has_2fa: false,
  is_agency_admin: false,
  agency: {
    id: 'a1',
    name: 'Alpha Agency',
    code: 'alpha',
    timezone: 'Asia/Manila',
    fiscal_year_start_month: 1,
    logo: false,
    setup_complete: true,
  },
  roles: [],
};
