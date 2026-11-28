import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { ME, mockApi } from '../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

it('opens the compact menu, focuses navigation, and returns focus on Escape', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
  });
  render(
    <MemoryRouter initialEntries={['/user-guide']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'User guide' });
  const user = userEvent.setup();
  const menu = screen.getByRole('button', { name: 'Menu' });
  await user.click(menu);
  expect(menu).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveFocus();
  await user.keyboard('{Escape}');
  expect(menu).toHaveAttribute('aria-expanded', 'false');
  expect(menu).toHaveFocus();
});

it('removed pages never appear in the menu', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
  });
  render(
    <MemoryRouter initialEntries={['/user-guide']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'User guide' });
  expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Plans to approve' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Who has reported' })).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Downloads' })).toBeInTheDocument();
});

it('the first Tab reaches a skip link that leads to the page content', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
    'GET /api/v1/fiscal-years': { body: [] },
  });
  render(
    <MemoryRouter initialEntries={['/user-guide']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'User guide' });
  await userEvent.setup().tab();
  const skip = screen.getByRole('link', { name: 'Skip to content' });
  expect(skip).toHaveFocus();
  expect(skip).toHaveAttribute('href', '#main-content');
  expect(document.getElementById('main-content')?.tagName).toBe('MAIN');
});

it('without sign-in there is no account menu or sign-out; with sign-in on there is', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, login_disabled: true } },
  });
  const { unmount } = render(
    <MemoryRouter initialEntries={['/user-guide']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'User guide' });
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  expect(screen.queryByRole('navigation', { name: 'Account' })).not.toBeInTheDocument();
  unmount();
  vi.unstubAllGlobals();
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, login_disabled: false } },
  });
  render(
    <MemoryRouter initialEntries={['/user-guide']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'User guide' });
  expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument();
});

it('the menu has only the pages a single officer needs', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true, login_disabled: true } },
    'GET /api/v1/progress': { status: 404, body: {} },
  });
  render(
    <MemoryRouter initialEntries={['/user-guide']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'User guide' });
  const links = screen
    .getAllByRole('link')
    .filter((a) => a.closest('nav[aria-label="Main"]'))
    .map((a) => a.textContent);
  expect(links).toEqual([
    'Step-by-step',
    'Dashboard',
    'Rankings',
    'Downloads',
    'Office plans',
    'Monthly results',
    'Offices',
    'Years',
    'User guide',
  ]);
});
