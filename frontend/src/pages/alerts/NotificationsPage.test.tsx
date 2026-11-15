import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const item = (id: string, title: string, read = false) => ({
  id,
  type: 'cutoff_reminder',
  title,
  body: 'The cutoff is in 5 days.',
  link: '/rankings',
  created_at: '2026-11-15T01:00:00Z',
  read_at: read ? '2026-11-15T02:00:00Z' : null,
});

function renderAt(path: string, routes: Record<string, unknown>) {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
    'GET /api/v1/fiscal-years': { body: [] },
    ...(routes as Record<string, { body: unknown }>),
  });
  render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return calls;
}

it('shows the unread count on the bell and follows a notification to its screen', async () => {
  const calls = renderAt('/notifications', {
    'GET /api/v1/notifications/unread-count': { body: { unread: 2 } },
    'GET /api/v1/notifications': {
      body: {
        results: [item('n1', 'DIV: January report due in 5 days'), item('n2', 'Old', true)],
        unread: 2,
      },
    },
    'POST /api/v1/notifications/n1/read': { body: { unread: 1 } },
    'GET /api/v1/rankings': { body: { sets: [], set: null, rows: [] } },
  });
  const user = userEvent.setup();
  const bell = await screen.findByRole('button', { name: 'Notifications, 2 unread' });
  await user.click(bell);
  const panel = await screen.findByRole('dialog', { name: 'Notifications' });
  await user.click(within(panel).getByRole('button', { name: /January report due/ }));
  expect(calls.some((c) => c.method === 'POST' && c.path === '/api/v1/notifications/n1/read')).toBe(
    true,
  );
  expect(await screen.findByRole('heading', { name: 'Rankings' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Notifications, 1 unread' })).toBeInTheDocument();
});

it('lists every notification and marks them all read', async () => {
  const calls = renderAt('/notifications', {
    'GET /api/v1/notifications': {
      body: { results: [item('n1', 'DIV: late'), item('n2', 'Old', true)], unread: 1 },
    },
    'POST /api/v1/notifications/read-all': { body: { unread: 0 } },
  });
  const user = userEvent.setup();
  expect(await screen.findByRole('link', { name: 'DIV: late' })).toHaveAttribute(
    'href',
    '/rankings',
  );
  expect(screen.getAllByRole('button', { name: 'Mark read' })).toHaveLength(1);
  await user.click(screen.getByRole('button', { name: 'Mark all read' }));
  expect(calls.some((c) => c.path === '/api/v1/notifications/read-all')).toBe(true);
});
