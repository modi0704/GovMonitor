import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { ME, mockApi } from '../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const USER = {
  id: 'u2',
  email: 'head@alpha.gov',
  full_name: 'Head',
  is_active: true,
  has_2fa: false,
  must_change_password: false,
  locked: false,
  last_login_at: null,
  created_at: '2026-01-01T00:00:00Z',
  assignments: [
    {
      id: 'ra1',
      office: { id: 's', code: 'SVC', name: 'Service' },
      level: 'admin',
      is_root: false,
    },
  ],
  is_agency_admin: false,
};

function renderUsers(me = { ...ME, is_agency_admin: true }) {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: me },
    'GET /api/v1/users': { body: [USER] },
    'GET /api/v1/offices': { body: [] },
    'GET /api/v1/users/u2/scope': {
      body: [{ id: 's', code: 'SVC', name: 'Service', depth: 1, can_edit: true }],
    },
    'POST /api/v1/users': {
      status: 201,
      body: {
        ...USER,
        id: 'u3',
        email: 'new@alpha.gov',
        assignments: [],
        temporary_password: 'Temp1234abcdWXYZ',
      },
    },
  });
  render(
    <MemoryRouter initialEntries={['/users']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return calls;
}

it('lists users with their access and shows a user’s effective scope', async () => {
  renderUsers();
  expect(await screen.findByText('Admin · SVC')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Head' }));
  const panel = screen.getByRole('complementary', { name: 'Selected user' });
  expect(await within(panel).findByText('can edit')).toBeInTheDocument();
});

it('creates a user and shows the temporary password once', async () => {
  const calls = renderUsers();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Add user' }));
  const dialog = screen.getByRole('dialog');
  await user.type(within(dialog).getByLabelText('Email'), 'new@alpha.gov');
  await user.click(within(dialog).getByRole('button', { name: 'Add user' }));
  expect(await screen.findByText('Temp1234abcdWXYZ')).toBeInTheDocument();
  expect(calls.find((c) => c.method === 'POST' && c.path === '/api/v1/users')?.body).toEqual({
    email: 'new@alpha.gov',
    full_name: '',
    assignments: [],
  });
});

it('tells other users the page is for the agency administrator', async () => {
  renderUsers({ ...ME, is_agency_admin: false });
  expect(
    await screen.findByText('Only the agency administrator can manage users.'),
  ).toBeInTheDocument();
});
