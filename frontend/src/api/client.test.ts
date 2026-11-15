import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, SESSION_EXPIRED_EVENT, api, readCookie } from './client';

function mockFetch(status: number, body: unknown) {
  const fn = vi
    .fn()
    .mockImplementation(() =>
      Promise.resolve(new Response(body === null ? '' : JSON.stringify(body), { status })),
    );
  vi.stubGlobal('fetch', fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'gm_csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT';
});

describe('api client', () => {
  it('reads cookies', () => {
    document.cookie = 'gm_csrftoken=abc123';
    expect(readCookie('gm_csrftoken')).toBe('abc123');
    expect(readCookie('missing')).toBeNull();
  });

  it('sends the CSRF header on unsafe methods only, with same-origin credentials', async () => {
    document.cookie = 'gm_csrftoken=tok';
    const fetchFn = mockFetch(200, { ok: true });
    await api.post('things', { a: 1 });
    const [url, init] = fetchFn.mock.calls[0]!;
    expect(url).toBe('/api/v1/things');
    expect(init.credentials).toBe('same-origin');
    expect(init.headers['X-CSRFToken']).toBe('tok');
    expect(init.headers['Content-Type']).toBe('application/json');
    await api.get('things', { page: 2, empty: '' });
    const [url2, init2] = fetchFn.mock.calls[1]!;
    expect(url2).toBe('/api/v1/things?page=2');
    expect(init2.headers['X-CSRFToken']).toBeUndefined();
  });

  it('raises ApiError with field errors and signals an expired session on 401', async () => {
    const listener = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, listener);
    mockFetch(401, { detail: 'Not signed in.' });
    await expect(api.get('me')).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledTimes(1);

    mockFetch(400, { email: ['Required.'] });
    const err = await api.post('x', {}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).fieldErrors).toEqual({ email: ['Required.'] });
    window.removeEventListener(SESSION_EXPIRED_EVENT, listener);
  });

  it('reports network failure as status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('net')));
    const err = await api.get('x').catch((e: unknown) => e);
    expect((err as ApiError).status).toBe(0);
  });
});
