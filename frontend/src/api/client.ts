/**
 * API client. Same-origin requests with the Django session cookie; unsafe methods send the CSRF
 * token from the `gm_csrftoken` cookie in the `X-CSRFToken` header (MASTERPLAN 5.1).
 */

export const API_BASE = '/api/v1';
const CSRF_COOKIE = 'gm_csrftoken';
const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, body: unknown, message?: string) {
    super(message ?? describeError(status, body));
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }

  /** Field errors from a DRF validation response, if any. */
  get fieldErrors(): Record<string, string[]> {
    if (this.body && typeof this.body === 'object' && !Array.isArray(this.body)) {
      const out: Record<string, string[]> = {};
      for (const [k, v] of Object.entries(this.body as Record<string, unknown>)) {
        if (k === 'detail' || k === 'code') continue;
        out[k] = Array.isArray(v) ? v.map(String) : [String(v)];
      }
      return out;
    }
    return {};
  }
}

function describeError(status: number, body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    return String((body as { detail: unknown }).detail);
  }
  if (status === 0) return 'Cannot reach the server. Check your connection and try again.';
  if (status >= 500) return 'The server had a problem. Please try again in a moment.';
  return `Request failed (${status}).`;
}

export function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(';')) {
    const item = part.trim();
    if (item.startsWith(prefix)) return decodeURIComponent(item.slice(prefix.length));
  }
  return null;
}

/** Fired when the server says the session is gone, so the app can show the sign-in page. */
export const SESSION_EXPIRED_EVENT = 'gm:session-expired';

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  signal?: AbortSignal;
  /** Do not raise the session-expired event on 401/403 (used by the sign-in calls). */
  quietAuth?: boolean;
  base?: string;
  /** Background poll: not shown by the loading bar. */
  background?: boolean;
}

// Requests in flight, for the shell's loading bar (P12.4). Background polls do not count.
let inFlight = 0;
const inFlightListeners = new Set<() => void>();
function setInFlight(delta: number) {
  inFlight = Math.max(0, inFlight + delta);
  inFlightListeners.forEach((fn) => fn());
}
export function subscribeInFlight(fn: () => void): () => void {
  inFlightListeners.add(fn);
  return () => inFlightListeners.delete(fn);
}
export function requestsInFlight(): number {
  return inFlight;
}

export async function apiRequest<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = (opts.method ?? 'GET').toUpperCase();
  const headers: Record<string, string> = { Accept: 'application/json' };
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) {
    body = opts.body;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }
  if (UNSAFE.has(method)) {
    const token = readCookie(CSRF_COOKIE);
    if (token) headers['X-CSRFToken'] = token;
  }
  let url = `${opts.base ?? API_BASE}/${path.replace(/^\//, '')}`;
  if (opts.query) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(opts.query)) {
      if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
    }
    const s = qs.toString();
    if (s) url += `?${s}`;
  }

  let response: Response;
  let text: string;
  if (!opts.background) setInFlight(1);
  try {
    try {
      response = await fetch(url, {
        method,
        headers,
        body,
        credentials: 'same-origin',
        signal: opts.signal,
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      throw new ApiError(0, null);
    }
    text = await response.text();
  } finally {
    if (!opts.background) setInFlight(-1);
  }
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    const code =
      data && typeof data === 'object' && 'code' in data ? (data as { code: unknown }).code : null;
    if (
      !opts.quietAuth &&
      (response.status === 401 || (response.status === 403 && code === 'not_authenticated'))
    ) {
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    }
    throw new ApiError(response.status, data);
  }
  return data as T;
}

export const api = {
  get: <T>(
    path: string,
    query?: RequestOptions['query'],
    signal?: AbortSignal,
    background = false,
  ) => apiRequest<T>(path, { query, signal, background }),
  post: <T>(path: string, body?: unknown, opts: Omit<RequestOptions, 'method' | 'body'> = {}) =>
    apiRequest<T>(path, { ...opts, method: 'POST', body }),
  put: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: 'PATCH', body }),
  del: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: 'DELETE', body }),
};
