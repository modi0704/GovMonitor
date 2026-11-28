import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const months = (...v: string[]) => [...v, ...Array(12 - v.length).fill('0')];
const PLAN = {
  id: 'p1',
  office: { id: 'o1', code: 'PME', name: 'Planning' },
  fiscal_year: { id: 'fy1', label: '2026' },
  version: 1,
  status: 'draft',
  approved_budget: null,
  planned_cost: '600000.00',
  can_edit: true,
  office_editable: true,
  weighting: 'cost_share',
  notes: '',
  periods: Array.from({ length: 12 }, (_, i) => ({
    month_index: i + 1,
    start_date: `2026-${String(i + 1).padStart(2, '0')}-01`,
    status: 'open',
  })),
  rows: [
    {
      id: 'out',
      parent: null,
      row_kind: 'output',
      code: 'O1',
      title: 'Output',
      sort_order: 10,
      measure_type: null,
      unit: '',
      annual_target: null,
      unit_cost: null,
      total_cost: null,
      manual_weight: null,
      implementing_office_id: null,
      targets: months(),
    },
    {
      id: 'a',
      parent: 'out',
      row_kind: 'activity',
      code: 'A',
      title: 'Visits',
      sort_order: 20,
      measure_type: 'quantity',
      unit: 'visit',
      annual_target: '10.0000',
      unit_cost: null,
      total_cost: '600000.00',
      manual_weight: null,
      implementing_office_id: 'o1',
      targets: months('2', '3', '5'),
    },
  ],
  indicators: [],
  issues: [],
};

function renderEditor() {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: ME },
    'GET /api/v1/plans/p1': { body: PLAN },
    'GET /api/v1/offices/directory': {
      body: [{ id: 'o1', code: 'PME', name: 'Planning', depth: 1 }],
    },
    'POST /api/v1/results/preview': {
      body: { weights: { a: '1' }, cum_plan: months('0.2', '0.5', '1'), funds_total: '600000' },
    },
    'POST /api/v1/plans/p1/save': { body: { plan: PLAN, created: {} } },
  });
  render(
    <MemoryRouter initialEntries={['/plans/p1']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return calls;
}

it('edits cells, pastes a block and saves only the changed rows', async () => {
  const calls = renderEditor();
  const user = userEvent.setup();
  const target = await screen.findByLabelText('Target, row 2');
  expect(target).toHaveValue('10');
  expect(screen.getByRole('button', { name: 'Saved' })).toBeDisabled();

  await user.clear(target);
  await user.type(target, '12');
  const feb = screen.getByLabelText('FEB, row 2');
  fireEvent.paste(feb, { clipboardData: { getData: () => '4\t5\t6' } });
  expect(screen.getByLabelText('APR, row 2')).toHaveValue('6');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  const save = calls.find((c) => c.path === '/api/v1/plans/p1/save')!.body as {
    rows: Record<string, unknown>[];
  };
  expect(save.rows).toHaveLength(1);
  expect(save.rows[0]).toMatchObject({ id: 'a', annual_target: '12', parent: 'out' });
  expect((save.rows[0]!.targets as string[]).slice(0, 4)).toEqual(['2', '4', '5', '6']);
});

it('undoes the last change and moves with the keyboard', async () => {
  renderEditor();
  const user = userEvent.setup();
  const title = await screen.findByLabelText('Title, row 2');
  await user.type(title, '!');
  expect(title).toHaveValue('Visits!');
  await user.click(screen.getByRole('button', { name: 'Undo' }));
  expect(screen.getByLabelText('Title, row 2')).toHaveValue('Visits');
  screen.getByLabelText('Title, row 1').focus();
  await user.keyboard('{ArrowDown}');
  expect(screen.getByLabelText('Title, row 2')).toHaveFocus();
});

it('adds an activity under the selected outline row', async () => {
  renderEditor();
  const user = userEvent.setup();
  await user.click(await screen.findByLabelText('Title, row 1'));
  await user.click(screen.getByRole('button', { name: 'Add below selected' }));
  const grid = screen.getByRole('table', { name: 'Plan activities' });
  expect(within(grid).getAllByRole('row')).toHaveLength(4); // header + 3 rows
  expect(screen.getByLabelText('Title, row 2')).toHaveValue('');
});

it('adds an indicator with monthly targets and saves it with the plan', async () => {
  const calls = renderEditor();
  const user = userEvent.setup();
  await user.click(await screen.findByRole('tab', { name: /Indicators/ }));
  await user.click(screen.getByRole('button', { name: 'Add indicator' }));
  await user.type(screen.getByLabelText('Indicator 1'), 'Reports published');
  await user.type(screen.getByLabelText('Annual target, indicator 1'), '4');
  await user.type(screen.getByLabelText('MAR, indicator 1'), '1');
  await user.selectOptions(screen.getByLabelText('Counted as, indicator 1'), 'last');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  const save = calls.find((c) => c.path === '/api/v1/plans/p1/save')!.body as {
    indicators: Record<string, unknown>[];
  };
  expect(save.indicators).toHaveLength(1);
  expect(save.indicators[0]).toMatchObject({
    name: 'Reports published',
    annual_target: '4',
    aggregation: 'last',
  });
  expect((save.indicators[0]!.targets as string[])[2]).toBe('1');
});

it('calculates the total cost from the target and the unit cost and does not let it be typed over', async () => {
  const calls = renderEditor();
  const user = userEvent.setup();
  const target = await screen.findByLabelText('Target, row 2');
  const unitCost = screen.getByLabelText('Unit cost, row 2');
  const total = screen.getByLabelText('Total cost, row 2');
  expect(total).toHaveValue('600000'); // saved lump sum: no unit cost, so it is typed in
  expect(total).not.toHaveAttribute('readonly');
  await user.type(unitCost, '5000');
  expect(total).toHaveValue('50000'); // 10 × 5000
  expect(total).toHaveAttribute('readonly');
  await user.clear(target);
  await user.type(target, '12');
  expect(total).toHaveValue('60000');
  await user.type(total, '9');
  expect(total).toHaveValue('60000');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  const save = calls.find((c) => c.path === '/api/v1/plans/p1/save')!.body as {
    rows: Record<string, unknown>[];
  };
  expect(save.rows[0]).toMatchObject({
    annual_target: '12',
    unit_cost: '5000',
    total_cost: '60000',
  });
});
