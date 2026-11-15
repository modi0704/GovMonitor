import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { ME, mockApi } from '../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

it('turns alert emails off for the signed-in user', async () => {
  let optOut = false;
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': () => ({ body: { ...ME, email_opt_out: optOut } }),
    'PATCH /api/v1/me': (body) => {
      optOut = (body as { email_opt_out: boolean }).email_opt_out;
      return { body: { ...ME, email_opt_out: optOut } };
    },
  });
  render(
    <MemoryRouter initialEntries={['/account/security']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  const box = await screen.findByLabelText(/daily email of my new notifications/);
  expect(box).toBeChecked();
  await user.click(box);
  expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ email_opt_out: true });
  expect(await screen.findByLabelText(/daily email of my new notifications/)).not.toBeChecked();
});
