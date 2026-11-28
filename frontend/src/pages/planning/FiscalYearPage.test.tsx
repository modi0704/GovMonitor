import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const period = (id: string, m: number, status: string) => ({
  id,
  month_index: m,
  start_date: `2026-0${m}-01`,
  end_date: `2026-0${m}-28`,
  cutoff_at: `2026-0${m + 1}-10T15:59:59Z`,
  status,
  locked_at: status === 'locked' ? '2026-02-11T00:00:00Z' : null,
});

function renderYear() {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true, login_disabled: true } },
    'GET /api/v1/fiscal-years/f1': {
      body: {
        id: 'f1',
        label: '2026',
        status: 'open',
        periods: [period('p1', 1, 'locked'), period('p2', 2, 'open'), period('p3', 3, 'open')],
      },
    },
    'POST /api/v1/periods/p2/lock': { body: { status: 'locked', results: 1 } },
    'POST /api/v1/periods/p1/unlock': { body: { status: 'open', results_removed: 1 } },
  });
  render(
    <MemoryRouter initialEntries={['/fiscal-years/f1']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return calls;
}

it('closes the next open month by hand and has no deadlines', async () => {
  const calls = renderYear();
  const user = userEvent.setup();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  const close = await screen.findAllByRole('button', { name: 'Close month' });
  expect(close).toHaveLength(1); // months close in order
  expect(screen.queryByRole('button', { name: 'Change deadline' })).not.toBeInTheDocument();
  expect(screen.queryByText(/deadline/i)).not.toBeInTheDocument();
  await user.click(close[0]!);
  expect(calls.some((c) => c.method === 'POST' && c.path === '/api/v1/periods/p2/lock')).toBe(true);
  expect(await screen.findByText(/February 2026 is closed/)).toBeInTheDocument();
});

it('reopens the latest closed month with a reason', async () => {
  const calls = renderYear();
  const user = userEvent.setup();
  vi.spyOn(window, 'prompt').mockReturnValue('Late figures from DIV');
  await user.click(await screen.findByRole('button', { name: 'Reopen month' }));
  expect(calls.find((c) => c.path === '/api/v1/periods/p1/unlock')?.body).toEqual({
    reason: 'Late figures from DIV',
  });
});
