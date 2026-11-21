import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { ME, mockApi } from '../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const ROOT = {
  id: 'r',
  parent_id: null,
  code: 'MIN',
  name: 'Ministry',
  depth: 0,
  level: { id: 'l0', name: 'Agency', depth: 0 },
  sort_order: 0,
  is_active: true,
  can_edit: true,
};

it('walks through levels, top office, offices and finishes', async () => {
  const me = { ...ME, is_agency_admin: true, agency: { ...ME.agency, setup_complete: false } };
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: me },
    'GET /api/v1/progress': {
      body: {
        steps: [],
        current: 'offices',
        offices_count: 0,
        root: null,
        fiscal_years: [],
        fiscal_year: null,
        plans: [],
        period: null,
        months: [],
        monthly: [],
      },
    },
    'GET /api/v1/levels': { body: [{ id: 'l0', depth: 0, name: 'Agency', office_count: 1 }] },
    'GET /api/v1/offices': { body: [ROOT] },
    'PUT /api/v1/levels': { body: [] },
    'PATCH /api/v1/offices/r': { body: { ...ROOT, name: 'Ministry of Things' } },
    'PATCH /api/v1/agency': { body: {} },
    'POST /api/v1/offices/import': { body: { rows: [], errors: [], created: 1 } },
  });
  render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  await user.click(await screen.findByRole('link', { name: 'Start the setup' }));
  await screen.findByDisplayValue('Agency'); // levels loaded
  await user.clear(screen.getByLabelText(/Level 1/));
  await user.type(screen.getByLabelText(/Level 1/), 'Ministry');
  await user.type(screen.getByLabelText('Level 2'), 'Division');
  await user.click(screen.getByRole('button', { name: 'Next' }));
  expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ names: ['Ministry', 'Division'] });
  const name = await screen.findByLabelText('Name');
  await user.clear(name);
  await user.type(name, 'Ministry of Things');
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await user.type(await screen.findByLabelText('Offices'), 'PME - Planning');
  await user.click(screen.getByRole('button', { name: 'Add offices and continue' }));
  await user.click(await screen.findByRole('button', { name: 'Finish setup' }));
  expect(calls.filter((c) => c.path === '/api/v1/agency').map((c) => c.body)).toEqual([
    { name: 'Ministry of Things' },
    { setup_complete: true },
  ]);
});
