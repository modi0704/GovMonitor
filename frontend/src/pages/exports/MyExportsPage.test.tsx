import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const job = (id: string, status: string, extra = {}) => ({
  id,
  kind: 'export_xlsx',
  status,
  params: { scope: 'subtree' },
  result: {},
  error: '',
  requested_by: 'ana@alpha.gov',
  created_at: '2026-11-15T03:00:00Z',
  finished_at: null,
  file_name: null,
  download_url: null,
  ...extra,
});

it('lists exports and polls while one is being prepared', async () => {
  let polls = 0;
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
    'GET /api/v1/jobs': () => {
      polls += 1;
      return {
        body:
          polls < 2
            ? [job('a', 'running'), job('b', 'failed', { error: 'ValueError: disk full' })]
            : [
                job('a', 'done', {
                  file_name: 'alpha-DIV-2026-Mar-2026.xlsx',
                  download_url: '/api/v1/jobs/a/download',
                }),
                job('b', 'failed', { error: 'ValueError: disk full' }),
              ],
      };
    },
  });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    render(
      <MemoryRouter initialEntries={['/exports']}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByText('Preparing…')).toBeInTheDocument();
    expect(screen.getByText('ValueError: disk full')).toBeInTheDocument();
    expect(screen.getAllByText('Office and the offices under it')).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(3100);
    const link = await screen.findByRole('link', { name: 'alpha-DIV-2026-Mar-2026.xlsx' });
    expect(link).toHaveAttribute('href', '/api/v1/jobs/a/download');
    const before = calls.filter((c) => c.path === '/api/v1/jobs').length;
    await vi.advanceTimersByTimeAsync(6500);
    // Nothing is pending any more: polling stops.
    expect(calls.filter((c) => c.path === '/api/v1/jobs').length).toBe(before);
  } finally {
    vi.useRealTimers();
  }
});
