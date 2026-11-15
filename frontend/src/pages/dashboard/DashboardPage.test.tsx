import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const ref = (id: string, code: string, depth = 1) => ({
  id,
  code,
  name: `${code} office`,
  depth,
  is_active: true,
});
const head = {
  cum_plan: '1',
  cum_actual: '0.8619',
  periodic_plan: '0',
  periodic_actual: '0.169',
  variance: '-0.1381',
  status: 'DELAYED',
  status_kind: 'delayed',
  funds_total: '55790100',
  funds_used_est: '48086600',
  funds_used_actual: null,
  funds_remaining: '7703500',
  indicator_score: null,
  final: true,
};
const sum = (v: string, rank: number) => ({
  cum_plan: '1',
  cum_actual: v,
  variance: '-0.1',
  status: 'DELAYED',
  status_kind: 'delayed',
  funds_total: '100',
  rank_sibling: rank,
});
const twelve = (v: string | null) => Array(12).fill(v);

function dashboard(officeId: string, views: string[] = ['owner']) {
  return {
    office: {
      ...ref(officeId, officeId === 'rds' ? 'RDS' : 'AST', 1),
      has_children: officeId === 'rds',
      ancestors: [ref('min', 'MIN', 0)],
    },
    period: {
      id: 'dec',
      month_index: 12,
      start_date: '2023-12-01',
      status: 'locked',
      fiscal_year: { id: 'f', label: '2023' },
    },
    months: Array.from({ length: 12 }, (_, i) => `2023-${String(i + 1).padStart(2, '0')}-01`),
    view: 'owner',
    views,
    final: true,
    label: 'FINAL',
    has_result: true,
    headline: head,
    rank_sibling: 1,
    plan_version: 1,
    series: { cum_plan: twelve('1'), cum_actual: twelve('0.8') },
    indicators: [],
    children:
      officeId === 'rds' ? [{ office: ref('ast', 'AST', 2), result: sum('0.5876', 3) }] : [],
    rankings: [],
    quarters: [
      {
        quarter: 4,
        first: 10,
        last: 12,
        partial: false,
        plan: '0.34',
        actual: '0.38',
        variance: '0.04',
        status: 'ADVANCED',
        status_kind: 'ahead',
      },
    ],
  };
}

function setup() {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, roles: [{ id: 'r', office_id: 'rds', level: 'admin' }] } },
    'GET /api/v1/fiscal-years': { body: [{ id: 'f', label: '2023', status: 'open' }] },
    'GET /api/v1/fiscal-years/f': {
      body: {
        id: 'f',
        label: '2023',
        status: 'open',
        periods: [{ id: 'dec', month_index: 12, start_date: '2023-12-01', status: 'locked' }],
      },
    },
    'GET /api/v1/offices': {
      body: [
        {
          id: 'rds',
          parent_id: null,
          code: 'RDS',
          name: 'RDS office',
          depth: 1,
          level: { id: 'l', name: 'S', depth: 1 },
          sort_order: 0,
          is_active: true,
          can_edit: true,
        },
      ],
    },
    'GET /api/v1/dashboard': () => {
      const last = calls.filter((c) => c.path === '/api/v1/dashboard').length;
      return { body: last > 1 ? dashboard('ast', ['owner', 'implementing']) : dashboard('rds') };
    },
    'GET /api/v1/dashboard/activities': {
      body: {
        activities: [
          {
            lineage_id: 'l1',
            code: 'AST-1',
            title: 'Fabrication',
            unit: 'unit',
            owner_office_code: 'AST',
            implementing_office_code: 'AST',
            annual_target: '4',
            weight: '0.5',
            planned_ratio: '1',
            actual_ratio: '0.5',
            variance: '-0.5',
            status_kind: 'delayed',
            cum_target: '4',
            cum_actual: '2',
            delay_reason: 'Late delivery',
            no_target: false,
          },
        ],
      },
    },
    'GET /api/v1/dashboard/activity': {
      body: {
        activity: {
          code: 'AST-1',
          title: 'Fabrication',
          unit: 'unit',
          annual_target: '4',
          owner_office: { code: 'AST' },
          implementing_office: { code: 'AST' },
        },
        months: [
          {
            month_index: 1,
            start_date: '2023-01-01',
            status: 'locked',
            planned: '1',
            actual: '1',
            remarks: 'ok',
            delay_reason: '',
            files: [{ id: 'x', file_name: 'proof.pdf', download_url: '/d' }],
          },
        ],
      },
    },
  });
  render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return calls;
}

it('shows the final figures and drills down to an office, its activities and their history', async () => {
  const calls = setup();
  const user = userEvent.setup();
  expect(await screen.findByRole('heading', { name: 'RDS office' })).toBeInTheDocument();
  expect(screen.getByText('FINAL')).toBeInTheDocument();
  expect(screen.getAllByText('86.19%').length).toBeGreaterThan(0);
  expect(screen.getByText(/Q4 \(OCT–DEC\)/)).toBeInTheDocument();
  expect(screen.getByText('ADVANCED')).toHaveClass('status-ahead');
  await user.click(screen.getByRole('button', { name: /AST AST office/ }));
  expect(await screen.findByRole('heading', { name: 'AST office' })).toBeInTheDocument();
  expect(calls.filter((c) => c.path === '/api/v1/dashboard')).toHaveLength(2);
  expect(screen.getByLabelText('Scores of')).toBeInTheDocument(); // both views available
  await user.click(screen.getByRole('tab', { name: 'Activities' }));
  expect(await screen.findByText('Late delivery')).toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: /AST-1 Fabrication/ }));
  const dialog = await screen.findByRole('dialog');
  expect(await within(dialog).findByRole('link', { name: 'proof.pdf' })).toBeInTheDocument();
});

it('offers every chart as a table', async () => {
  setup();
  await screen.findByRole('heading', { name: 'RDS office' });
  const buttons = screen.getAllByRole('button', { name: 'View as table' });
  expect(buttons.length).toBe(2);
  await userEvent.click(buttons[1]!);
  expect(screen.getAllByText('₱48,086,600.00')).toHaveLength(2); // the funds tile and the table
});
