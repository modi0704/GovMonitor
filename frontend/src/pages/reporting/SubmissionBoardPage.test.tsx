import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

it('shows who has not submitted and locks the month', async () => {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/fiscal-years': { body: [{ id: 'f1', label: '2026', status: 'open' }] },
    'GET /api/v1/fiscal-years/f1': {
      body: {
        id: 'f1',
        label: '2026',
        status: 'open',
        periods: [{ id: 'm1', month_index: 1, start_date: '2026-01-01', status: 'open' }],
      },
    },
    'GET /api/v1/submission-board': {
      body: {
        period: {
          id: 'm1',
          start_date: '2026-01-01',
          cutoff_at: '2026-02-10T15:59:59Z',
          status: 'open',
          locked_at: null,
          locked_by: null,
          days_to_cutoff: 3,
          can_lock: true,
          can_unlock: false,
        },
        offices: [
          {
            office: { id: 'a', code: 'PME', name: 'Planning', depth: 2 },
            plan_version: 1,
            status: 'submitted',
            submitted_at: '2026-02-01T00:00:00Z',
            submitted_by: 'pme@a.gov',
          },
          {
            office: { id: 'b', code: 'HRM', name: 'Human Resources', depth: 2 },
            plan_version: 1,
            status: 'draft',
          },
        ],
        not_submitted: [{ id: 'b', code: 'HRM', name: 'Human Resources' }],
      },
    },
    'POST /api/v1/periods/m1/lock': { body: { status: 'locked', results: 5 } },
  });
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
  render(
    <MemoryRouter initialEntries={['/submissions']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  expect(await screen.findByText(/Not submitted yet \(1\):/)).toBeInTheDocument();
  expect(screen.getByText('Cutoff in 3 day(s)')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Lock January 2026' }));
  expect(confirm.mock.calls[0]![0]).toMatch(/1 office\(s\) have not submitted/);
  expect(calls.some((c) => c.method === 'POST' && c.path === '/api/v1/periods/m1/lock')).toBe(true);
  expect(await screen.findByText('January 2026 is locked.')).toBeInTheDocument();
});
