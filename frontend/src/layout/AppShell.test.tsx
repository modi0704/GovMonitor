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
    <MemoryRouter initialEntries={['/help']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'Help' });
  const user = userEvent.setup();
  const menu = screen.getByRole('button', { name: 'Menu' });
  await user.click(menu);
  expect(menu).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveFocus();
  await user.keyboard('{Escape}');
  expect(menu).toHaveAttribute('aria-expanded', 'false');
  expect(menu).toHaveFocus();
});

it('keeps agency management destinations out of a read-only user navigation', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
  });
  render(
    <MemoryRouter initialEntries={['/help']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'Help' });
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
    <MemoryRouter initialEntries={['/notifications']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'Notifications' });
  await userEvent.setup().tab();
  const skip = screen.getByRole('link', { name: 'Skip to content' });
  expect(skip).toHaveFocus();
  expect(skip).toHaveAttribute('href', '#main-content');
  expect(document.getElementById('main-content')?.tagName).toBe('MAIN');
});

it.each([
  [
    'expiring',
    false,
    'The licence expires on 25 November 2026 (10 days left).',
    'Ask your administrator to renew it.',
  ],
  [
    'expired',
    true,
    'The licence expired on 1 November 2026: the system is read-only.',
    'You can still sign in',
  ],
])('shows the licence banner when %s', async (status, readOnly, message, hint) => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': {
      body: {
        ...ME,
        licence: {
          status,
          read_only: readOnly,
          expires: null,
          days_left: null,
          seats: 10,
          seats_used: 3,
          message,
        },
      },
    },
  });
  render(
    <MemoryRouter initialEntries={['/notifications']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const banner = (await screen.findByText(new RegExp(message.slice(0, 20)))).closest(
    '.licence-banner',
  )!;
  expect(banner).toHaveAttribute('role', readOnly ? 'alert' : 'status');
  expect(banner).toHaveTextContent(message);
  expect(banner).toHaveTextContent(hint);
});

it('testing mode: no sign-out button, and a notice that sign-in is off', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, login_disabled: true } },
  });
  render(
    <MemoryRouter initialEntries={['/help']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  await screen.findByRole('heading', { name: 'Help' });
  expect(screen.queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();
  expect(screen.getByText(/Testing mode: sign-in is switched off/)).toBeInTheDocument();
});
