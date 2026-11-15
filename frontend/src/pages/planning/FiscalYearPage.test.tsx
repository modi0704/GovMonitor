import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

it('lets the agency administrator move one month’s cutoff', async () => {
  const period = (id: string, m: number, status: string) => ({
    id,
    month_index: m,
    start_date: `2026-0${m}-01`,
    end_date: `2026-0${m}-28`,
    cutoff_at: `2026-0${m + 1}-10T15:59:59Z`,
    status,
    locked_at: status === 'locked' ? '2026-02-11T00:00:00Z' : null,
  });
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/fiscal-years/f1': {
      body: {
        id: 'f1',
        label: '2026',
        status: 'open',
        periods: [period('p1', 1, 'locked'), period('p2', 2, 'open')],
      },
    },
    'PATCH /api/v1/periods/p2': { body: {} },
  });
  render(
    <MemoryRouter initialEntries={['/fiscal-years/f1']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  const buttons = await screen.findAllByRole('button', { name: 'Change cutoff' });
  expect(buttons).toHaveLength(1); // the locked month keeps its cutoff
  await user.click(buttons[0]!);
  await user.click(screen.getByRole('button', { name: 'Save' }));
  const body = calls.find((c) => c.method === 'PATCH')!.body as { cutoff_at: string };
  expect(body.cutoff_at).toMatch(/^2026-03-10T/);
});
