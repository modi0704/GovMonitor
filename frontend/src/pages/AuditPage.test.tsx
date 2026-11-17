import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { ME, mockApi } from '../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const ROW = {
  id: 7,
  at: '2026-11-15T03:00:00Z',
  actor_type: 'user',
  actor_id: 'u1',
  actor: 'boss@alpha.gov',
  action: 'update',
  entity_type: 'office',
  entity_id: 'o1',
  office_id: null,
  ip: '127.0.0.1',
  changed: ['name'],
};

it('lists entries, filters by action and shows before/after', async () => {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/users': { body: [] },
    'GET /api/v1/offices': { body: [] },
    'GET /api/v1/audit-log': {
      body: {
        results: [ROW],
        next_before: null,
        actions: ['login', 'update'],
        entity_types: ['office'],
      },
    },
    'GET /api/v1/audit-log/7': {
      body: { ...ROW, before: { name: 'Old' }, after: { name: 'New' } },
    },
  });
  render(
    <MemoryRouter initialEntries={['/audit']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Updated' }));
  const dialog = await screen.findByRole('dialog');
  expect(within(dialog).getByText('Old')).toBeInTheDocument();
  expect(within(dialog).getByText('New')).toBeInTheDocument();
  await user.keyboard('{Escape}');
  await user.selectOptions(screen.getByLabelText('Action'), 'login');
  await user.click(screen.getByRole('button', { name: 'Apply' }));
  expect(calls.some((c) => c.path === '/api/v1/audit-log' && c.method === 'GET')).toBe(true);
  expect(screen.getByRole('link', { name: 'Download CSV' })).toHaveAttribute(
    'href',
    '/api/v1/audit-log/export.csv?action=login',
  );
});
