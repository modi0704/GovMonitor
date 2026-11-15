import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

const level = (depth: number, name: string) => ({ id: `l${depth}`, name, depth });
const OFFICES = [
  {
    id: 'r',
    parent_id: null,
    code: 'MIN',
    name: 'Ministry',
    depth: 0,
    level: level(0, 'Ministry'),
    sort_order: 0,
    is_active: true,
    can_edit: true,
  },
  {
    id: 's1',
    parent_id: 'r',
    code: 'SVC1',
    name: 'Service One',
    depth: 1,
    level: level(1, 'Service'),
    sort_order: 10,
    is_active: true,
    can_edit: true,
  },
  {
    id: 'd1',
    parent_id: 's1',
    code: 'DIV1',
    name: 'Division One',
    depth: 2,
    level: level(2, 'Division'),
    sort_order: 10,
    is_active: true,
    can_edit: true,
  },
];

afterEach(() => vi.unstubAllGlobals());

function renderStructure(me = { ...ME, is_agency_admin: true }) {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: me },
    'GET /api/v1/offices': { body: OFFICES },
    'GET /api/v1/levels': { body: [] },
    'POST /api/v1/offices': { status: 201, body: {} },
    'POST /api/v1/offices/import': (body) => ({
      body: {
        rows: (body as { rows: { code: string; name: string }[] }).rows.map((r, i) => ({
          row: i + 1,
          code: r.code,
          name: r.name,
          parent_code: 'SVC1',
        })),
        errors: [],
        created: 0,
      },
    }),
  });
  render(
    <MemoryRouter initialEntries={['/structure']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return calls;
}

it('shows the tree and collapses a branch', async () => {
  renderStructure();
  const tree = await screen.findByRole('tree', { name: 'Offices' });
  expect(await within(tree).findByText('Division One')).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Collapse Service One' }));
  expect(within(tree).queryByText('Division One')).not.toBeInTheDocument();
});

it('lets the agency administrator add an office beneath the selected one', async () => {
  const calls = renderStructure();
  const user = userEvent.setup();
  await user.click(await screen.findByText('Service One'));
  await user.click(screen.getByRole('button', { name: 'Add an office beneath' }));
  const dialog = screen.getByRole('dialog');
  await user.type(within(dialog).getByLabelText('Name'), 'Planning');
  await user.type(within(dialog).getByLabelText(/Code/), 'PLN');
  await user.click(within(dialog).getByRole('button', { name: 'Add office' }));
  expect(calls.find((c) => c.method === 'POST' && c.path === '/api/v1/offices')?.body).toEqual({
    parent_id: 's1',
    name: 'Planning',
    code: 'PLN',
  });
});

it('previews a pasted list before saving', async () => {
  renderStructure();
  const user = userEvent.setup();
  await user.click(await screen.findByText('Service One'));
  await user.click(screen.getByRole('button', { name: 'Paste a list of offices beneath' }));
  const dialog = screen.getByRole('dialog');
  await user.type(within(dialog).getByLabelText('Offices to add'), 'U1, Unit One');
  expect(within(dialog).getByRole('button', { name: 'Add offices' })).toBeDisabled();
  await user.click(within(dialog).getByRole('button', { name: 'Preview' }));
  expect(await within(dialog).findByText('Unit One')).toBeInTheDocument();
  expect(within(dialog).getByRole('button', { name: 'Add offices' })).toBeEnabled();
});

it('hides editing actions from users who are not the agency administrator', async () => {
  renderStructure({ ...ME, is_agency_admin: false });
  await userEvent.click(await screen.findByText('Service One'));
  expect(
    screen.getByText('Only the agency administrator can change the structure.'),
  ).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add an office beneath' })).not.toBeInTheDocument();
});
