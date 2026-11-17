import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const PROFILE = {
  id: 'p1',
  fiscal_year_id: 'fy1',
  version: 1,
  locked_months: 1,
  preset: 'workbook_compatible',
  weighting: 'cost_share',
  cap_at_100: false,
  on_time_tolerance: '0E-10',
  label_ahead: 'ADVANCED',
  label_on_time: 'ON-TIME',
  label_delayed: 'DELAYED',
  rollup: 'budget_weighted',
  indicator_weighting: 'equal',
  indicator_rollup: 'all_indicators',
  ranking_metric: 'cumulative_actual',
  mov_required: false,
  auto_lock: false,
  cutoff_day: 10,
  show_actual_amounts: false,
};

it('asks for confirmation when months are locked, then saves', async () => {
  let attempts = 0;
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/fiscal-years/fy1': {
      body: {
        id: 'fy1',
        label: '2026',
        profile_id: 'p1',
        status: 'open',
        start_date: '2026-01-01',
        end_date: '2026-12-31',
        preset: 'workbook_compatible',
      },
    },
    'GET /api/v1/scoring-presets': {
      body: [{ name: 'workbook_compatible', description: 'Workbook', settings: {} }],
    },
    'GET /api/v1/scoring-profiles/p1': { body: PROFILE },
    'PATCH /api/v1/scoring-profiles/p1': () => {
      attempts += 1;
      return attempts === 1
        ? {
            status: 409,
            body: { detail: 'Some months are locked. Confirm?', code: 'confirm_required' },
          }
        : { body: { ...PROFILE, cap_at_100: true, version: 2 } };
    },
  });
  const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
  render(
    <MemoryRouter initialEntries={['/fiscal-years/fy1/scoring']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  await user.click(await screen.findByRole('checkbox', { name: 'Limit scores to 100%' }));
  await user.click(screen.getByRole('button', { name: 'Save settings' }));
  expect(await screen.findByText('Saved (version 2).')).toBeInTheDocument();
  expect(confirm).toHaveBeenCalledWith('Some months are locked. Confirm?');
  const patches = calls
    .filter((c) => c.method === 'PATCH')
    .map((c) => c.body as { confirm: boolean; cap_at_100: boolean });
  expect(patches.map((p) => [p.cap_at_100, p.confirm])).toEqual([
    [true, false],
    [true, true],
  ]);
  confirm.mockRestore();
});
