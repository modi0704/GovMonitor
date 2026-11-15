import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import { ME, mockApi } from '../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

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
