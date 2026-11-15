import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const HEAD = {
  cum_plan: '0.12',
  cum_actual: '0.06',
  periodic_plan: '0.12',
  periodic_actual: '0.06',
  variance: '-0.06',
  status: 'DELAYED',
  status_kind: 'delayed',
  funds_total: '1000000',
  funds_used_est: '60000',
  funds_used_actual: null,
  funds_remaining: '940000',
  indicator_score: null,
};
const ACT = {
  lineage_id: 'la',
  code: 'A',
  title: 'Visits',
  unit: 'visit',
  measure_type: 'quantity',
  annual_target: '10',
  owner_office: { id: 'o1', code: 'DIV' },
  implementing_office: { id: 'o1', code: 'DIV' },
  target_month: '2',
  cum_target: '2',
  prev_cum_actual: '0',
  actual: '1',
  actual_amount: null,
  remarks: '',
  delay_reason: '',
  attachments: 0,
  planned_ratio: '0.2',
  actual_ratio: '0.1',
  behind: true,
  no_target: false,
  editable: true,
};
const REPORT = {
  office: { id: 'o1', code: 'DIV', name: 'Division' },
  view: 'owner',
  has_plan: true,
  plan_id: 'p1',
  period: {
    id: 'm1',
    month_index: 1,
    start_date: '2026-01-01',
    cutoff_at: '2026-02-10T15:59:59Z',
    status: 'open',
    fiscal_year: { id: 'f1', label: '2026' },
  },
  submission: { status: 'draft' },
  can_submit: true,
  can_return: false,
  mov_required: false,
  show_amounts: true,
  activities: [ACT],
  indicators: [],
  result: HEAD,
};

function renderPage(overrides = {}) {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
    'GET /api/v1/fiscal-years': { body: [{ id: 'f1', label: '2026', status: 'open' }] },
    'GET /api/v1/fiscal-years/f1': {
      body: {
        id: 'f1',
        label: '2026',
        status: 'open',
        periods: [{ id: 'm1', month_index: 1, start_date: '2026-01-01', status: 'open' }],
      },
    },
    'GET /api/v1/offices': {
      body: [
        {
          id: 'o1',
          parent_id: null,
          code: 'DIV',
          name: 'Division',
          depth: 1,
          level: { id: 'l', name: 'D', depth: 1 },
          sort_order: 0,
          is_active: true,
          can_edit: true,
        },
      ],
    },
    'GET /api/v1/reports': { body: REPORT },
    'POST /api/v1/reports/preview': {
      body: {
        result: {
          ...HEAD,
          cum_actual: '0.2',
          periodic_actual: '0.2',
          variance: '0.08',
          status: 'ADVANCED',
          status_kind: 'ahead',
        },
      },
    },
    'POST /api/v1/reports/save': {
      body: { ...REPORT, activities: [{ ...ACT, actual: '2', behind: false }] },
    },
    'POST /api/v1/reports/submit': {
      status: 400,
      body: {
        detail: 'Fix 1 problem(s) before submitting.',
        code: 'cannot_submit',
        problems: [
          {
            code: 'delay_reason',
            row: 'la',
            message: 'A: behind plan — give the reason for the delay.',
          },
        ],
      },
    },
    'GET /api/v1/attachments': {
      body: [
        {
          id: 'f',
          file_name: 'photo.jpg',
          size_bytes: 2048,
          uploaded_by: 'div@a.gov',
          uploaded_at: '2026-01-05T00:00:00Z',
          download_url: '/x',
        },
      ],
    },
    ...overrides,
  });
  render(
    <MemoryRouter initialEntries={['/reports']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return calls;
}

it('shows the month, updates the live result as numbers are typed, and saves the edited row', async () => {
  const calls = renderPage();
  const user = userEvent.setup();
  const done = await screen.findByLabelText('Done this month, A');
  expect(done).toHaveValue('1');
  expect(screen.getByLabelText('Reason for delay, A')).toHaveAttribute('placeholder', 'Required');
  expect(screen.getByText('DELAYED')).toHaveClass('status-delayed');
  await user.clear(done);
  await user.type(done, '2');
  expect(await screen.findByText('ADVANCED', {}, { timeout: 2000 })).toHaveClass('status-ahead');
  expect(screen.getByText(/includes numbers not saved yet/)).toBeInTheDocument();
  await user.type(screen.getByLabelText('Amount spent, A'), '50000');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  const save = calls.find((c) => c.path === '/api/v1/reports/save')!.body as {
    activities: unknown[];
  };
  expect(save.activities).toEqual([{ lineage_id: 'la', actual: '2', actual_amount: '50000' }]);
  expect(await screen.findByText('Saved.')).toBeInTheDocument();
});

it('lists what stops submission', async () => {
  renderPage();
  const user = userEvent.setup();
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  await user.click(await screen.findByRole('button', { name: 'Submit report' }));
  expect(await screen.findByText(/stop the report from being submitted/)).toBeInTheDocument();
  expect(
    screen.getAllByText('A: behind plan — give the reason for the delay.').length,
  ).toBeGreaterThan(0);
});

it('opens the supporting files of a row', async () => {
  renderPage();
  await userEvent.click(await screen.findByRole('button', { name: 'Attach' }));
  const dialog = await screen.findByRole('dialog');
  expect(await within(dialog).findByText('photo.jpg')).toBeInTheDocument();
  expect(within(dialog).getByLabelText('Choose files to attach')).toHaveAttribute(
    'accept',
    '.pdf,.jpg,.jpeg,.png,.docx,.xlsx,.pptx',
  );
});
