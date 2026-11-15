import { apiRequest, type RequestOptions } from '../api/client';

const BASE = '/platform/api';

/** The platform owner's API: separate session, never triggers the agency session-expired flow. */
export const platformApi = {
  get: <T>(path: string) => apiRequest<T>(path, { base: BASE, quietAuth: true }),
  post: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, { base: BASE, method: 'POST', body, quietAuth: true }),
  patch: <T>(path: string, body?: unknown) =>
    apiRequest<T>(path, { base: BASE, method: 'PATCH', body, quietAuth: true }),
  request: <T>(path: string, opts: RequestOptions) =>
    apiRequest<T>(path, { ...opts, base: BASE, quietAuth: true }),
};
