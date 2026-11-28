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
    'GET /api/v1/offices': { body: [] },
    'GET /api/v1/levels': { body: [] },
  });
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

const PLAN = '5f0c2a52-8d3e-4b6f-9a51-0d6f2a7c1e11';

it.each(['/structure', '/reports', `/plans/${PLAN}`, '/setup'])(
  'on a phone, %s says to open it on a computer and hides editing links',
  async (path) => {
    phone(true);
    renderAt(path);
    expect(
      await screen.findByRole('heading', { name: 'Open on a computer to edit' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Offices' })).toHaveClass('desktop-only');
    expect(screen.getByRole('link', { name: 'Rankings' })).not.toHaveClass('desktop-only');
  },
);

it('on a computer the page itself is shown', async () => {
  phone(false);
  renderAt('/structure');
  expect(await screen.findByRole('heading', { name: 'Offices' })).toBeInTheDocument();
  expect(screen.queryByText('Open on a computer to edit')).not.toBeInTheDocument();
});
