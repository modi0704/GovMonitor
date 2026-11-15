import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import type { Period } from '../../api/types';
import { mockApi } from '../../test/mockApi';
import ExportDialog from './ExportDialog';

afterEach(() => vi.unstubAllGlobals());

const PERIODS: Period[] = (
  [
    { id: 'nov', month_index: 11, start_date: '2023-11-01', status: 'locked' },
    { id: 'dec', month_index: 12, start_date: '2023-12-01', status: 'open' },
  ] as const
).map((p) => ({ ...p, end_date: p.start_date, cutoff_at: p.start_date, locked_at: null }));

const job = (status: string, extra = {}) => ({
  id: 'j1',
  kind: 'export_xlsx',
  status,
  params: {},
  result: {},
  error: '',
  requested_by: 'ana@alpha.gov',
  created_at: '2026-11-15T03:00:00Z',
  finished_at: null,
  file_name: null,
  download_url: null,
  ...extra,
});

it('queues an export with the chosen scope, month and view, then offers the file', async () => {
  let polls = 0;
  const calls = mockApi({
    'POST /api/v1/exports/xlsx': { status: 202, body: job('queued') },
    'GET /api/v1/jobs/j1': () => {
      polls += 1;
      return {
        body:
          polls < 2
            ? job('running')
            : job('done', { file_name: 'most-RDS.xlsx', download_url: '/api/v1/jobs/j1/download' }),
      };
    },
  });
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(
      <MemoryRouter>
        <ExportDialog
          officeId="rds"
          officeLabel="RDS Research"
          periods={PERIODS}
          periodId="dec"
          view="owner"
          canExportAgency={false}
          onClose={() => {}}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByLabelText('The whole agency')).not.toBeInTheDocument();
    await user.click(screen.getByLabelText('RDS Research and every office beneath it'));
    await user.selectOptions(screen.getByLabelText('Month'), 'nov');
    await user.selectOptions(screen.getByLabelText('Scores of'), 'implementing');
    await user.click(screen.getByRole('button', { name: 'Prepare workbook' }));
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      scope: 'subtree',
      office_id: 'rds',
      period_id: 'nov',
      view: 'implementing',
    });
    expect(await screen.findByText('Waiting')).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(4100);
    const link = await screen.findByRole('link', { name: 'Download most-RDS.xlsx' });
    expect(link).toHaveAttribute('href', '/api/v1/jobs/j1/download');
    expect(screen.getByRole('link', { name: 'My exports' })).toHaveAttribute('href', '/exports');
  } finally {
    vi.useRealTimers();
  }
});
