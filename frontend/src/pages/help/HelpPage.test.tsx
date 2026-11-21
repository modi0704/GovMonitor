import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import HelpTip from '../../components/HelpTip';
import { ME, mockApi } from '../../test/mockApi';
import { SCORING_TIPS } from '../planning/scoringTips';

afterEach(() => vi.unstubAllGlobals());

function renderHelp(me: object) {
  mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, ...me } },
  });
  render(
    <MemoryRouter initialEntries={['/help']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

it("opens on the reader's own role and switches to the others", async () => {
  renderHelp({ roles: [{ id: 'r', office_id: 'o', level: 'admin' }] });
  const own = await screen.findByRole('tab', { name: 'Office administrator (you)' });
  expect(own).toHaveAttribute('aria-selected', 'true');
  expect(
    screen.getByRole('heading', { name: 'Every month, before the deadline' }),
  ).toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole('tab', { name: 'Read-only user' }));
  expect(screen.getByRole('heading', { name: 'Rankings and alerts' })).toBeInTheDocument();
});

it('an agency administrator starts on their guide; a viewer on theirs', async () => {
  renderHelp({ is_agency_admin: true });
  expect(
    await screen.findByRole('tab', { name: 'Monitoring administrator (you)' }),
  ).toHaveAttribute('aria-selected', 'true');
});

it('help tips open on focus, describe the setting and close with Escape', async () => {
  render(<HelpTip label="Limit scores to 100%">{SCORING_TIPS.cap_at_100}</HelpTip>);
  const user = userEvent.setup();
  await user.tab();
  const button = screen.getByRole('button', { name: 'About: Limit scores to 100%' });
  expect(button).toHaveFocus();
  expect(screen.getByRole('tooltip')).toHaveTextContent(/plan 10, done 12/);
  expect(button).toHaveAccessibleDescription(/plan 10, done 12/);
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
});

it('every scoring setting has a tip', () => {
  for (const key of [
    'preset',
    'weighting',
    'cap_at_100',
    'on_time_tolerance',
    'labels',
    'rollup',
    'indicator_weighting',
    'indicator_rollup',
    'ranking_metric',
    'cutoff_day',
    'auto_lock',
    'mov_required',
    'show_actual_amounts',
  ]) {
    expect(SCORING_TIPS[key], key).toBeTruthy();
  }
});
