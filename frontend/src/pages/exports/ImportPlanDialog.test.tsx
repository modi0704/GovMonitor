import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import { mockApi } from '../../test/mockApi';
import ImportPlanDialog from './ImportPlanDialog';

afterEach(() => vi.unstubAllGlobals());

const job = (status: string, result = {}, error = '') => ({
  id: 'j1',
  kind: 'import_plan',
  status,
  params: {},
  result,
  error,
  requested_by: 'ana@alpha.gov',
  created_at: '2026-11-15T03:00:00Z',
  finished_at: null,
  file_name: null,
  download_url: null,
});

function renderDialog(onImported = vi.fn()) {
  render(
    <MemoryRouter>
      <ImportPlanDialog
        office={{ id: 'o1', code: 'OTHER', name: 'Other office' }}
        fiscalYear={{ id: 'f1', label: '2026' }}
        onClose={() => {}}
        onImported={onImported}
      />
    </MemoryRouter>,
  );
  return onImported;
}

async function chooseAndImport() {
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  const file = new File(['PK'], 'plan.xlsx');
  await user.upload(screen.getByLabelText('Excel file (.xlsx)'), file);
  await user.click(screen.getByRole('button', { name: 'Import' }));
}

it('offers the template and lists the problems of a rejected file row by row', async () => {
  mockApi({
    'POST /api/v1/imports/plan': { status: 202, body: job('queued') },
    'GET /api/v1/jobs/j1': {
      body: job(
        'failed',
        {
          errors: [
            { row: 10, column: 'I', message: "I10: 'four' is not a number." },
            { row: 20, column: 'N', message: 'This ACTUAL row has no PLAN row above it.' },
          ],
        },
        '2 problem(s) in the file; nothing was imported.',
      ),
    },
  });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    renderDialog();
    expect(screen.getByRole('link', { name: 'import template' })).toHaveAttribute(
      'href',
      '/api/v1/imports/plan-template?fiscal_year_id=f1&office_id=o1',
    );
    await chooseAndImport();
    await vi.advanceTimersByTimeAsync(2100);
    expect(await screen.findByText("I10: 'four' is not a number.")).toBeInTheDocument();
    expect(screen.getByText('2 problem(s) in the file; nothing was imported.')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '20' })).toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

it('links to the new draft plan when the import succeeds', async () => {
  const calls = mockApi({
    'POST /api/v1/imports/plan': { status: 202, body: job('queued') },
    'GET /api/v1/jobs/j1': {
      body: job('done', { plan_id: 'p9', activities: 3, warnings: [] }),
    },
  });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    const onImported = renderDialog();
    await chooseAndImport();
    expect(calls.find((c) => c.method === 'POST')?.path).toBe('/api/v1/imports/plan');
    await vi.advanceTimersByTimeAsync(2100);
    expect(await screen.findByRole('link', { name: 'Open the draft plan' })).toHaveAttribute(
      'href',
      '/plans/p9',
    );
    expect(onImported).toHaveBeenCalled();
  } finally {
    vi.useRealTimers();
  }
});
