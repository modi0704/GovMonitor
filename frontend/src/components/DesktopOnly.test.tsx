import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { ME, mockApi } from '../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

function phone(matches: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function renderAt(path: string) {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/users': { body: [] },
    'GET /api/v1/offices': { body: [] },
    'GET /api/v1/audit-log': {
      body: { results: [], next_before: null, actions: [], entity_types: [] },
    },
  });
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

it.each(['/structure', '/users', '/audit', '/reports', '/plans/p1', '/settings/alerts'])(
  'on a phone, %s says to open it on a computer and hides editing links',
  async (path) => {
    phone(true);
    renderAt(path);
    expect(
      await screen.findByRole('heading', { name: 'Open on a computer to edit' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Users' })).toHaveClass('desktop-only');
    expect(screen.getByRole('link', { name: 'Rankings' })).not.toHaveClass('desktop-only');
  },
);

it('on a computer the page itself is shown', async () => {
  phone(false);
  renderAt('/audit');
  expect(await screen.findByRole('heading', { name: 'Change history' })).toBeInTheDocument();
  expect(screen.queryByText('Open on a computer to edit')).not.toBeInTheDocument();
});
