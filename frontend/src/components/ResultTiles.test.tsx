import { render, screen } from '@testing-library/react';
import type { Headline } from '../api/types';
import ResultPanel from './ResultTiles';

const result: Headline = {
  periodic_actual: '0.1',
  periodic_plan: '0.08',
  cum_actual: '0.3',
  cum_plan: '0.25',
  variance: '0.05',
  status: 'AHEAD',
  funds_total: '100000',
  funds_used_est: '30000',
  funds_used_actual: null,
  funds_remaining: '70000',
  indicator_score: null,
};

it('distinguishes plan comparison from an actual previous-month comparison', () => {
  render(
    <ResultPanel
      result={result}
      monthLabel="March 2027"
      history={{
        actual: ['0.1', '0.2', '0.3'],
        planned: ['0.08', '0.16', '0.25'],
        month: 3,
      }}
    />,
  );
  expect(screen.getByText(/\+2.00 points/)).toBeInTheDocument();
  expect(screen.getByText(/\+10.00 points/)).toBeInTheDocument();
  expect(screen.getByText('vs last month')).toBeInTheDocument();
  expect(screen.getByText('30.0% used')).toBeInTheDocument();
});

it('does not invent a previous-month change or draw missing and future observations', () => {
  render(
    <ResultPanel
      result={result}
      monthLabel="March 2027"
      history={{
        actual: ['0.1', null, '0.3', '0.9'],
        planned: ['0.08', '0.16', '0.25', '0.4'],
        month: 3,
      }}
    />,
  );
  expect(screen.queryByText('vs last month')).not.toBeInTheDocument();
  const plot = screen.getByRole('img', { name: 'Progress to date: actual and planned history' });
  expect(plot.querySelectorAll('circle')).toHaveLength(2);
  const path = plot.querySelector('.sparkline-actual')?.getAttribute('d');
  expect(path?.match(/M/g)).toHaveLength(2);
});

it('shows an honest empty budget and no history when only monthly report data is available', () => {
  const { container } = render(
    <ResultPanel
      result={{ ...result, funds_total: '0', funds_used_est: '0' }}
      monthLabel="March 2027"
    />,
  );
  expect(screen.getByText('No budget')).toBeInTheDocument();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(container.textContent).not.toMatch(/NaN|Infinity/);
});

it('does not display a negative zero from harmless decimal rounding', () => {
  render(
    <ResultPanel
      result={{ ...result, periodic_actual: '0.29999999999999999', periodic_plan: '0.3' }}
      monthLabel="March 2027"
    />,
  );
  expect(screen.getByText(/0.00 points/)).toHaveClass('trend-neutral');
  expect(screen.queryByText(/-0.00 points/)).not.toBeInTheDocument();
});
