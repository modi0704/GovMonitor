import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const office = (id: string, code: string) => ({ id, code, name: code, depth: 2, is_active: true });
const row = (
  id: string,
  code: string,
  rank: number | null,
  value: string | null,
  change: number | null,
) => ({
  office: office(id, code),
  rank,
  value,
  previous_rank: null,
  change,
  result: value
    ? {
        cum_plan: '1',
        cum_actual: value,
        variance: '0',
        status: 'ON-TIME',
        status_kind: 'on_time',
        funds_total: '1',
        rank_sibling: rank,
      }
    : null,
});

it('shows a ranking with changes and switches set', async () => {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
    'GET /api/v1/fiscal-years': { body: [{ id: 'f', label: '2023', status: 'open' }] },
    'GET /api/v1/fiscal-years/f': {
      body: {
        id: 'f',
        label: '2023',
        status: 'open',
        periods: [{ id: 'dec', month_index: 12, start_date: '2023-12-01', status: 'locked' }],
      },
    },
    'GET /api/v1/rankings': {
      body: {
        sets: [
          { key: 'children:x', kind: 'children', name: 'Offices under RDS' },
          { key: 'group:g', kind: 'group', name: 'Island centers' },
        ],
        set: { key: 'children:x', name: 'Offices under RDS' },
        metric: 'cumulative_actual',
        label: 'FINAL',
        previous_month: '2023-11-01',
        rows: [
          row('a', 'RDI', 1, '0.9907', 0),
          row('b', 'ILD', 2, '0.9023', 1),
          row('c', 'AST', 3, '0.5876', -1),
          row('d', 'NEW', null, null, null),
        ],
      },
    },
  });
  render(
    <MemoryRouter initialEntries={['/rankings']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  expect(await screen.findByText('99.07%')).toBeInTheDocument();
  expect(screen.getByText('▲ 1')).toBeInTheDocument();
  expect(screen.getByText('▼ 1')).toBeInTheDocument();
  expect(screen.getByText('No result')).toBeInTheDocument();
  expect(screen.getByText(/Change is against November 2023/)).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText('Ranking'), 'group:g');
  expect(calls.some((c) => c.path === '/api/v1/rankings')).toBe(true);
});
