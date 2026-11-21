import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';
import type { Progress } from './GuidedStepsPage';

afterEach(() => vi.unstubAllGlobals());

const ADMIN = { ...ME, is_agency_admin: true, roles: [{ office_id: 'root', level: 'admin' }] };
const office = (id: string, code: string, name: string) => ({ id, code, name, depth: 1 });

const PROGRESS: Progress = {
  steps: [
    { key: 'offices', done: true },
    { key: 'year', done: true },
    { key: 'plans', done: false, started: true },
    { key: 'results', done: false },
    { key: 'review', done: false },
    { key: 'report', done: false },
  ],
  current: 'plans',
  offices_count: 3,
  root: { id: 'root', code: 'MIN', name: 'Ministry', depth: 0 },
  fiscal_years: [{ id: 'fy', label: '2026', status: 'open' }],
  fiscal_year: { id: 'fy', label: '2026', status: 'open' },
  plans: [
    {
      office: office('pme', 'PME', 'Planning'),
      plan_id: 'p1',
      status: 'approved',
      activities: 6,
      indicators: 2,
      budget: null,
    },
    {
      office: office('hrm', 'HRM', 'Human resources'),
      plan_id: 'p2',
      status: 'draft',
      activities: 4,
      indicators: 0,
      budget: null,
    },
    {
      office: office('gas', 'GAS', 'General services'),
      plan_id: null,
      status: 'none',
      activities: 0,
      indicators: 0,
      budget: null,
    },
  ],
  period: { id: 'jan', month_index: 1, start_date: '2026-01-01', status: 'open' },
  months: [
    {
      id: 'jan',
      month_index: 1,
      start_date: '2026-01-01',
      status: 'open',
      offices_done: 0,
      offices_total: 1,
    },
  ],
  monthly: [{ office: office('pme', 'PME', 'Planning'), status: 'draft' }],
};

function renderHome(progress = PROGRESS, extra = {}) {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ADMIN },
    'GET /api/v1/progress': { body: progress },
    ...extra,
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

it('opens on the current step with a progress bar and the office checklist', async () => {
  renderHome();
  expect(await screen.findByRole('heading', { name: 'Step-by-step' })).toBeInTheDocument();
  expect(screen.getByRole('progressbar', { name: 'Steps done' })).toHaveAttribute(
    'aria-valuenow',
    '33',
  );
  expect(screen.getByText(/Step 3 of 6: Enter each office's plan/)).toBeInTheDocument();
  expect(screen.getByText('Before you start, collect from the offices')).toBeInTheDocument();
  const gas = screen.getByRole('row', { name: /GAS/ });
  expect(within(gas).getByText('Not started')).toBeInTheDocument();
  expect(within(gas).getByRole('button', { name: 'Start plan' })).toBeInTheDocument();
  const pme = screen.getByRole('row', { name: /PME/ });
  expect(within(pme).getByText('Final')).toBeInTheDocument();
});

it('marks a plan as final in one click (submit, then approve)', async () => {
  const calls = renderHome(PROGRESS, {
    'POST /api/v1/plans/p2/submit': { body: {} },
    'POST /api/v1/plans/p2/approve': { body: {} },
  });
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  const user = userEvent.setup();
  const hrm = await screen.findByRole('row', { name: /HRM/ });
  await user.click(within(hrm).getByRole('button', { name: 'Mark as final' }));
  expect(await screen.findByText('The plan of Human resources is final.')).toBeInTheDocument();
  expect(calls.filter((c) => c.method === 'POST').map((c) => c.path)).toEqual([
    '/api/v1/plans/p2/submit',
    '/api/v1/plans/p2/approve',
  ]);
});

it('moves to the next step and links each office to its monthly results', async () => {
  renderHome();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: /Next: Enter the monthly results/ }));
  expect(screen.getByText(/Step 4 of 6: Enter the monthly results/)).toBeInTheDocument();
  const pme = screen.getByRole('row', { name: /PME/ });
  expect(within(pme).getByText('Being entered')).toBeInTheDocument();
  expect(within(pme).getByRole('link', { name: 'Enter results' })).toHaveAttribute(
    'href',
    '/reports?fy=fy&office=pme&period=jan',
  );
});
