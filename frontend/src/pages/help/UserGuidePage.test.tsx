import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UserGuidePage from './UserGuidePage';
import GuideContent from './GuideContent';

it('shows only the user guide, with PDF and print options and no command or practice downloads', () => {
  render(<UserGuidePage />);
  expect(screen.getByRole('heading', { name: 'Overview & Roles' })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Download PDF' })).toHaveAttribute(
    'href',
    '/user-guide/USER_GUIDE.pdf',
  );
  expect(
    screen.getAllByRole('link').filter((link) => link.getAttribute('href')?.endsWith('.txt')),
  ).toHaveLength(0);
  expect(screen.getByRole('button', { name: 'Print section' })).toBeInTheDocument();
  expect(screen.queryByText('Run & close')).not.toBeInTheDocument();
  expect(screen.queryByText('Practice input')).not.toBeInTheDocument();
  expect(screen.queryByText(/Windows commands/)).not.toBeInTheDocument();
});

it('searches section contents and opens the selected control reference', async () => {
  render(<UserGuidePage />);
  const user = userEvent.setup();
  await user.type(screen.getByRole('searchbox', { name: 'Find a topic' }), 'Quarter details');
  const contents = screen.getByRole('navigation', { name: 'User guide sections' });
  await user.click(
    within(contents).getByRole('button', { name: 'Dashboard: Filters, Results & Office Detail' }),
  );
  expect(
    screen.getByRole('heading', { name: 'Dashboard: Filters, Results & Office Detail' }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole('columnheader', { name: 'What it means and how to use it' }),
  ).toBeInTheDocument();
  await user.clear(screen.getByRole('searchbox'));
  await user.type(screen.getByRole('searchbox'), 'there-is-no-such-topic');
  expect(screen.getByText(/No matching topic/)).toBeInTheDocument();
});

it('renders guide text safely and retains usable table and list structure', () => {
  const { container } = render(
    <GuideContent
      markdown={
        '### Example\n\n<img src=x onerror=alert(1)>\n\n[Unsafe](javascript:alert)\n\n| A | B |\n|---|---|\n| One | Two |\n\n1. Read\n2. Save'
      }
    />,
  );
  expect(container.querySelector('img')).toBeNull();
  expect(container.querySelector('a')).toBeNull();
  expect(screen.getAllByRole('columnheader')).toHaveLength(2);
  expect(screen.getAllByRole('listitem')).toHaveLength(2);
});
