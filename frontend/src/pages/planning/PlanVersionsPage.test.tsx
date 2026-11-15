import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const v = (id: string, version: number, status: string) => ({
  id,
  version,
  status,
  office: { id: 'o', code: 'PME', name: 'Planning' },
  fiscal_year: { id: 'f', label: '2026' },
  approved_budget: null,
  planned_cost: '100',
  submitted_at: null,
  submitted_by: null,
  approved_at: null,
  approved_by: null,
  updated_at: '2026-01-01T00:00:00Z',
  can_edit: false,
  office_editable: true,
});

it('lists versions and shows what changed', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
    'GET /api/v1/plans/v2/versions': { body: [v('v2', 2, 'draft'), v('v1', 1, 'approved')] },
    'GET /api/v1/plans/v2/compare': {
      body: {
        from_version: 1,
        to_version: 2,
        added: [{ lineage_id: 'd', code: 'D', title: 'New activity' }],
        removed: [{ lineage_id: 'c', code: 'C', title: 'Dropped' }],
        changed: [
          {
            lineage_id: 'a',
            code: 'A',
            title: 'Visits',
            changes: { annual_target: { before: '10', after: '12' } },
          },
        ],
      },
    },
  });
  render(
    <MemoryRouter initialEntries={['/plans/v2/versions']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await userEvent.click(await screen.findByRole('button', { name: 'Compare with version 1' }));
  expect(await screen.findByText('Version 1 → version 2')).toBeInTheDocument();
  expect(screen.getByText('New activity')).toBeInTheDocument();
  expect(screen.getByText('Dropped')).toBeInTheDocument();
  expect(screen.getByText('12')).toBeInTheDocument();
});
