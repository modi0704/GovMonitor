import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

it('shows the rule in percentage points and saves it as a share', async () => {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/alert-rules': {
      body: {
        remind_days_before: [5, 1],
        delay_threshold: '0.05',
        email_enabled: false,
        email_available: false,
      },
    },
    'PATCH /api/v1/alert-rules': { body: {} },
  });
  render(
    <MemoryRouter initialEntries={['/settings/alerts']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  const days = await screen.findByLabelText(/days before the deadline/);
  expect(days).toHaveValue('5, 1');
  const threshold = screen.getByLabelText(/behind plan by more than/);
  expect(threshold).toHaveValue(5);
  expect(screen.getByLabelText(/daily email summary/)).toBeDisabled();
  expect(screen.getByText(/Email is not set up/)).toBeInTheDocument();
  await user.clear(days);
  await user.type(days, '7, 2');
  await user.clear(threshold);
  await user.type(threshold, '10');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
    remind_days_before: '7, 2',
    delay_threshold: '0.1',
    email_enabled: false,
  });
});
