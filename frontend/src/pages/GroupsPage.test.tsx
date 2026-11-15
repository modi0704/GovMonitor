import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { ME, mockApi } from '../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const lv = { id: 'l', name: 'L', depth: 1 };
const OFFICES = [
  {
    id: 'a',
    parent_id: null,
    code: 'A',
    name: 'Alpha',
    depth: 1,
    level: lv,
    sort_order: 0,
    is_active: true,
    can_edit: true,
  },
  {
    id: 'b',
    parent_id: null,
    code: 'B',
    name: 'Beta',
    depth: 1,
    level: lv,
    sort_order: 1,
    is_active: true,
    can_edit: true,
  },
];

it('creates a group with members', async () => {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/groups': { body: [] },
    'GET /api/v1/offices': { body: OFFICES },
    'POST /api/v1/groups': {
      status: 201,
      body: { id: 'g1', name: 'Mainland', description: '', sort_order: 0, members: [] },
    },
    'PUT /api/v1/groups/g1/members': { body: {} },
  });
  render(
    <MemoryRouter initialEntries={['/groups']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  expect(await screen.findByText(/No groups yet/)).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'New group' }));
  const dialog = screen.getByRole('dialog');
  await user.type(within(dialog).getByLabelText('Name'), 'Mainland');
  await user.click(within(dialog).getByRole('checkbox', { name: /Beta/ }));
  await user.click(within(dialog).getByRole('button', { name: 'Save group' }));
  expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ office_ids: ['b'] });
});
