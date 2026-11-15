import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

it("offers to copy last year's approved plan into the new year", async () => {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
    'GET /api/v1/fiscal-years': {
      body: [
        { id: 'f27', label: '2027', status: 'draft' },
        { id: 'f26', label: '2026', status: 'open' },
      ],
    },
    'GET /api/v1/offices': {
      body: [
        {
          id: 'o1',
          parent_id: null,
          code: 'PME',
          name: 'Planning',
          depth: 1,
          level: { id: 'l', name: 'D', depth: 1 },
          sort_order: 0,
          is_active: true,
          can_edit: true,
        },
      ],
    },
    'GET /api/v1/plans': (_b) => ({ body: [] }),
    'POST /api/v1/plans/old/copy': { status: 201, body: { id: 'new' } },
    'GET /api/v1/plans/new': { status: 404, body: {} },
  });
  // The previous year's approved plans come from the same endpoint with a fiscal_year filter.
  const fetchMock = globalThis.fetch as unknown as { mock: { calls: unknown[] } };
  const original = globalThis.fetch;
  vi.stubGlobal('fetch', (url: string, init?: RequestInit) =>
    url.includes('fiscal_year=f26')
      ? Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: 'old',
                version: 1,
                status: 'approved',
                office: { id: 'o1', code: 'PME', name: 'Planning' },
                fiscal_year: { id: 'f26', label: '2026' },
              },
            ]),
          ),
        )
      : original(url, init),
  );
  render(
    <MemoryRouter initialEntries={['/plans?fy=f27']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  await userEvent.click(await screen.findByRole('button', { name: 'Copy from 2026' }));
  expect(calls.some((c) => c.method === 'POST' && c.path === '/api/v1/plans/old/copy')).toBe(true);
  expect(fetchMock).toBeDefined();
});
