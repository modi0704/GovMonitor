import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from './App';
import { SESSION_EXPIRED_EVENT } from './api/client';
import { AuthProvider } from './auth/AuthContext';
import { ME, mockApi } from './test/mockApi';

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

it('sends signed-out visitors to the sign-in page', async () => {
  mockApi({ 'GET /api/v1/auth/csrf': { body: { ok: true } } });
  renderAt('/');
  expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
});

it('signs in with email and password and lands on the home page', async () => {
  let signedIn = false;
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: { ok: true } },
    'GET /api/v1/me': () => (signedIn ? { body: ME } : { status: 401, body: {} }),
    'POST /api/v1/auth/login': () => {
      signedIn = true;
      return { body: { status: 'ok', me: ME } };
    },
  });
  renderAt('/sign-in');
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText('Email'), 'ana@alpha.gov');
  await user.type(screen.getByLabelText('Password'), 'secret-password-1');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByRole('heading', { name: 'Welcome, Ana' })).toBeInTheDocument();
  expect(calls.find((c) => c.path === '/api/v1/auth/login')?.body).toEqual({
    email: 'ana@alpha.gov',
    password: 'secret-password-1',
  });
});

it('asks for the two-step code when the account has 2FA', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: { ok: true } },
    'POST /api/v1/auth/login': { body: { status: '2fa_required' } },
    'POST /api/v1/auth/2fa': (body) =>
      (body as { code: string }).code === '123456'
        ? { body: { status: 'ok', me: ME } }
        : { status: 400, body: { detail: 'The code is not correct.', code: 'invalid_code' } },
  });
  renderAt('/sign-in');
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText('Email'), 'ana@alpha.gov');
  await user.type(screen.getByLabelText('Password'), 'secret-password-1');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  await user.type(await screen.findByLabelText('Code'), '000000');
  await user.click(screen.getByRole('button', { name: 'Verify' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('The code is not correct.');
  await user.clear(screen.getByLabelText('Code'));
  await user.type(screen.getByLabelText('Code'), '123456');
  await user.click(screen.getByRole('button', { name: 'Verify' }));
  expect(await screen.findByRole('heading', { name: 'Welcome, Ana' })).toBeInTheDocument();
});

it('forces a password change before anything else', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: { ok: true } },
    'GET /api/v1/me': { body: { ...ME, must_change_password: true } },
  });
  renderAt('/account/security');
  expect(await screen.findByRole('heading', { name: 'Choose a new password' })).toBeInTheDocument();
});

it('shows the session-expired message when the server ends the session', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: { ok: true } },
    'GET /api/v1/me': { body: ME },
  });
  renderAt('/');
  expect(await screen.findByRole('heading', { name: 'Welcome, Ana' })).toBeInTheDocument();
  act(() => {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
  });
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument());
  expect(screen.getByRole('status')).toHaveTextContent('You were signed out');
});

it('never redirects to another site after sign-in', async () => {
  mockApi({
    'GET /api/v1/auth/csrf': { body: { ok: true } },
    'POST /api/v1/auth/login': { body: { status: 'ok', me: ME } },
  });
  renderAt('/sign-in?next=//evil.example');
  const user = userEvent.setup();
  await user.type(await screen.findByLabelText('Email'), 'a@b.c');
  await user.type(screen.getByLabelText('Password'), 'x');
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  expect(await screen.findByRole('heading', { name: 'Welcome, Ana' })).toBeInTheDocument();
});

it('shows a not-found page for unknown routes', () => {
  mockApi({});
  renderAt('/nope');
  expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument();
});
