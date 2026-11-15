import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const plan = (id: string, code: string, status: string, budget: string | null, cost: string) => ({
  id,
  version: 1,
  status,
  office: { id: `o-${code}`, code, name: code },
  fiscal_year: { id: 'f', label: '2026' },
  approved_budget: budget,
  planned_cost: cost,
  submitted_at: '2026-01-05T00:00:00Z',
  submitted_by: 'head@a.gov',
  approved_at: null,
  approved_by: null,
  updated_at: '2026-01-05T00:00:00Z',
  can_edit: false,
  office_editable: true,
});

it('approves from the queue and shows budget against planned cost', async () => {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/fiscal-years': { body: [{ id: 'f', label: '2026', status: 'open' }] },
    'GET /api/v1/plans': {
      body: [
        plan('p1', 'PME', 'submitted', null, '100'),
        plan('p2', 'HRM', 'approved', '80', '100'),
      ],
    },
    'POST /api/v1/plans/p1/approve': { body: {} },
  });
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  render(
    <MemoryRouter initialEntries={['/plans/approvals']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  expect(await screen.findByText(/over budget/)).toHaveTextContent('-20.00 over budget');
  await userEvent.click(screen.getByRole('button', { name: 'Approve' }));
  expect(calls.some((c) => c.method === 'POST' && c.path === '/api/v1/plans/p1/approve')).toBe(
    true,
  );
});
