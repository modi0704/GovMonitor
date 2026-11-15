import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach } from 'vitest';
import App from '../../App';
import { AuthProvider } from '../../auth/AuthContext';
import { ME, mockApi } from '../../test/mockApi';

afterEach(() => vi.unstubAllGlobals());

const TEMPLATE = {
  kind: 'pptx',
  settings: {
    report_title: 'Performance Monitoring Report',
    primary_color: '1F4E79',
    accent_color: 'F2C14E',
    footer_text: '',
  },
  customised: false,
  logo_url: null,
  updated_at: null,
};

it('edits the title and footer and saves them', async () => {
  const calls = mockApi({
    'GET /api/v1/auth/csrf': { body: {} },
    'GET /api/v1/me': { body: { ...ME, is_agency_admin: true } },
    'GET /api/v1/export-templates/pptx': { body: TEMPLATE },
    'PATCH /api/v1/export-templates/pptx': { body: { ...TEMPLATE, customised: true } },
  });
  render(
    <MemoryRouter initialEntries={['/settings/report-template']}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  const user = userEvent.setup();
  const title = await screen.findByLabelText('Report title');
  expect(screen.getByText(/using the system default/)).toBeInTheDocument();
  await user.clear(title);
  await user.type(title, 'Quarterly Review');
  await user.type(screen.getByLabelText('Footer text'), 'Internal');
  expect(screen.getByLabelText('Header preview')).toHaveTextContent('Quarterly Review');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({
    report_title: 'Quarterly Review',
    primary_color: '1F4E79',
    accent_color: 'F2C14E',
    footer_text: 'Internal',
  });
  expect(await screen.findByText(/New exports use these settings/)).toBeInTheDocument();
  expect(screen.getByText('No logo yet. It appears on the title slide.')).toBeInTheDocument();
});
