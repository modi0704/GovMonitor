import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expectNoHorizontalScroll } from './helpers';

/**
 * P12.7 — smoke tests for the five user flows of MASTERPLAN section 12.
 *
 * Desktop runs every flow on a brand-new agency created through the platform owner screens (so
 * repeated runs never collide). The phone project then uses that agency for what a phone is for
 * (D12): following results, attaching a photo, downloading an export — and checks that editing
 * screens say to use a computer and that no page scrolls sideways.
 *
 * Needs a running server with a worker (exports) and a platform owner:
 *   PLATFORM_EMAIL / PLATFORM_PASSWORD (defaults below), SMOKE_BASE_URL.
 */

const PLATFORM = {
  email: process.env.PLATFORM_EMAIL ?? 'ops@govmonitor.test',
  password: process.env.PLATFORM_PASSWORD ?? 'platform-smoke-pass-2026',
};
const NEW_PASSWORD = 'smoke-test-password-2026';
// Outside test-results/, which Playwright empties at the start of every run.
const STATE_FILE = join(tmpdir(), 'govmonitor-smoke-state.json');

interface State {
  code: string;
  admin: string;
  officeAdmin: string;
  viewer: string;
  fyId: string;
  janId: string;
  febId: string;
}

function saveState(state: State) {
  writeFileSync(STATE_FILE, JSON.stringify(state));
}

function loadState(): State | null {
  return existsSync(STATE_FILE) ? (JSON.parse(readFileSync(STATE_FILE, 'utf8')) as State) : null;
}

async function api<T = unknown>(
  page: Page,
  method: string,
  path: string,
  data?: unknown,
): Promise<T> {
  const cookies = await page.context().cookies();
  const csrf = cookies.find((c) => c.name === 'gm_csrftoken')?.value ?? '';
  const res = await page.request.fetch(`/api/v1/${path}`, {
    method,
    data,
    headers: { 'X-CSRFToken': csrf, Referer: page.url() },
  });
  expect(res.ok(), `${method} ${path}: ${res.status()} ${await res.text()}`).toBeTruthy();
  return (await res.json().catch(() => null)) as T;
}

async function signIn(page: Page, email: string, password = NEW_PASSWORD) {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  if (password === NEW_PASSWORD) {
    await expect(page).not.toHaveURL(/sign-in/);
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  }
}

/** First sign-in with a temporary password: the user must choose their own. */
async function firstSignIn(page: Page, email: string, temporary: string) {
  await signIn(page, email, temporary);
  await page.getByLabel('Temporary password').fill(temporary);
  await page.getByLabel('New password', { exact: true }).fill(NEW_PASSWORD);
  await page.getByLabel('Repeat the new password').fill(NEW_PASSWORD);
  await page.getByRole('button', { name: 'Save password' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

async function temporaryPassword(page: Page): Promise<string> {
  const code = page.locator('code').first();
  await expect(code).toBeVisible();
  return (await code.textContent())!.trim();
}

test.describe.serial('desktop: the five flows', () => {
  // eslint-disable-next-line no-empty-pattern -- Playwright needs the fixtures argument destructured
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== 'desktop', 'set-up and planning are desktop work (D12)');
  });
  const stamp = Date.now().toString(36);
  const code = `smoke-${stamp}`;
  const admin = `chief@${code}.test`;
  const officeAdmin = `pme@${code}.test`;
  const viewer = `viewer@${code}.test`;
  let fyId = '';
  let periods: { id: string; month_index: number }[] = [];
  let planId = '';
  let lineages: string[] = [];

  test('1. agency setup', async ({ page }) => {
    page.on('dialog', (d) => d.accept());
    await page.goto('/platform/sign-in');
    await page.getByLabel('Email').fill(PLATFORM.email);
    await page.getByLabel('Password').fill(PLATFORM.password);
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page.getByRole('heading', { name: 'Agencies' })).toBeVisible();
    await page.getByLabel('Name', { exact: true }).fill(`Smoke Agency ${stamp}`);
    await page.getByLabel(/^Code/).fill(code);
    await page.getByLabel(/Name of the top level/).fill('Department');
    await page.getByRole('button', { name: 'Create agency' }).click();
    const row = page.getByRole('row', { name: new RegExp(code) });
    await row.getByRole('button', { name: 'Add administrator' }).click();
    await page.getByLabel('Email', { exact: true }).fill(admin);
    await page.getByLabel('Full name').fill('Smoke Chief');
    await page.getByRole('button', { name: 'Create administrator' }).click();
    const temporary = await temporaryPassword(page);
    await page.getByRole('button', { name: 'Sign out' }).click();

    await firstSignIn(page, admin, temporary);
    // Levels, top office, offices.
    await page.getByRole('link', { name: 'Start the setup' }).click();
    await page.getByLabel('Level 2').fill('Division');
    await page.getByRole('button', { name: 'Next' }).click();
    await page.getByLabel('Name', { exact: true }).fill('Department of Smoke');
    await page.getByRole('button', { name: 'Next' }).click();
    await page.getByLabel('Offices').fill('PME - Planning and Monitoring\nHRD - Human Resources');
    await page.getByRole('button', { name: 'Add offices and continue' }).click();
    await page.getByRole('button', { name: 'Finish setup' }).click();

    // Fiscal year with a scoring preset, opened; then the cutoff day.
    await page.goto('/fiscal-years');
    await page.getByRole('button', { name: 'New fiscal year' }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Create' }).click();
    await page.getByRole('button', { name: 'Open', exact: true }).click();
    await expect(page.getByText('open', { exact: true })).toBeVisible();
    const years = await api<{ id: string; status: string }[]>(page, 'GET', 'fiscal-years');
    fyId = years[0]!.id;
    await page.goto(`/fiscal-years/${fyId}/scoring`);
    await page.getByRole('spinbutton', { name: 'Monthly report deadline day' }).fill('12');
    await page.getByRole('button', { name: /^Save/ }).click();
    await expect(page.getByText(/Saved|saved/).first()).toBeVisible();
    const fy = await api<{ periods: { id: string; month_index: number }[] }>(
      page,
      'GET',
      `fiscal-years/${fyId}`,
    );
    periods = fy.periods;

    // Users: an office administrator for PME and a read-only user for the whole agency.
    const passwords: Record<string, string> = {};
    for (const [email, office, level] of [
      [officeAdmin, 'PME', 'admin'],
      [viewer, 'Department of Smoke', 'read_only'],
    ] as const) {
      await page.goto('/users');
      await page.getByRole('button', { name: 'Add user' }).click();
      const dialog = page.getByRole('dialog');
      await dialog.getByLabel('Email').fill(email);
      await dialog.getByLabel('Full name').fill(email.split('@')[0]!);
      const select = dialog.getByLabel('Office');
      const option = select.locator('option', { hasText: office }).first();
      await select.selectOption({ value: (await option.getAttribute('value'))! });
      await dialog.getByLabel('Level').selectOption(level);
      await dialog.getByRole('button', { name: 'Add user' }).click();
      passwords[email] = await temporaryPassword(page);
    }
    await page.getByRole('button', { name: 'Sign out' }).click();
    for (const email of [officeAdmin, viewer]) {
      await firstSignIn(page, email, passwords[email]!);
      await page.getByRole('button', { name: 'Sign out' }).click();
    }
  });

  test('2. planning', async ({ page, browser }) => {
    page.on('dialog', (d) => d.accept());
    await signIn(page, officeAdmin);
    await page.goto('/plans');
    await page
      .getByRole('row', { name: /PME/ })
      .getByRole('button', { name: 'Start empty plan' })
      .click();
    await expect(page).toHaveURL(/\/plans\/[0-9a-f-]+$/);
    planId = page.url().split('/').pop()!;
    // Enter the plan (the grid sends this same request), with one mistake to fix.
    const rows = [
      {
        client_key: 'o',
        row_kind: 'output',
        code: 'O1',
        title: 'Services delivered',
        sort_order: 0,
      },
      ...[
        ['A', 'Training courses', '600000', '10', ['2', '3', '5']],
        ['B', 'Manuals', '300000', '4', ['0', '2', '1']], // adds up to 3, not 4
        ['C', 'Forum', '100000', '1', ['0', '0', '1']],
      ].map(([c, title, cost, target, months], i) => ({
        client_key: c,
        parent: 'o',
        row_kind: 'activity',
        code: c,
        title,
        sort_order: (i + 1) * 10,
        measure_type: 'quantity',
        unit: 'unit',
        annual_target: target,
        total_cost: cost,
        targets: [...(months as string[]), ...Array(9).fill('0')],
      })),
    ];
    const saved = await api<{ plan: { rows: { id: string; code: string; lineage_id: string }[] } }>(
      page,
      'POST',
      `plans/${planId}/save`,
      { rows },
    );
    await page.reload();
    // Submitting shows what must be fixed first.
    await page.getByRole('button', { name: 'Submit for approval' }).click();
    await expect(page.getByText(/problem\(s\) must be fixed before submitting/)).toBeVisible();
    await expect(page.getByText(/add up to 3, not the annual target 4/)).toBeVisible();
    const b = saved.plan.rows.find((r) => r.code === 'B')!;
    await api(page, 'POST', `plans/${planId}/save`, {
      rows: [{ id: b.id, targets: ['0', '2', '2', ...Array(9).fill('0')] }],
    });
    await page.reload();
    lineages = saved.plan.rows.filter((r) => r.code !== 'O1').map((r) => r.lineage_id);
    await page.getByRole('button', { name: 'Submit for approval' }).click();
    await expect(page.getByText(/Waiting for approval|submitted/i).first()).toBeVisible();

    const chief = await browser.newPage();
    chief.on('dialog', (d) => d.accept());
    await signIn(chief, admin);
    await chief.getByRole('button', { name: /Notifications, \d+ unread/ }).click();
    await expect(chief.getByText(/PME: plan .* waits for approval/)).toBeVisible();
    await chief.goto('/plans/approvals');
    await chief.getByRole('button', { name: 'Approve' }).first().click();
    await chief.goto('/plans');
    await expect(chief.getByRole('row', { name: /PME/ }).getByText('Approved')).toBeVisible();
    await chief.close();
  });

  test('3. monthly cycle', async ({ page, browser }) => {
    page.on('dialog', (d) => d.accept());
    const jan = periods.find((p) => p.month_index === 1)!;
    await signIn(page, officeAdmin);
    const offices = await api<{ id: string; code: string }[]>(page, 'GET', 'offices');
    const pme = offices.find((o) => o.code === 'PME')!;
    await page.goto(`/reports?fy=${fyId}&office=${pme.id}&period=${jan.id}`);
    await page.getByLabel('Done this month, A').fill('1'); // planned 2: behind
    await page.getByLabel('Reason for delay, A').fill('Venue not available');
    await page.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible();
    // Supporting file for activity A.
    await page
      .getByRole('button', { name: /Attach/ })
      .first()
      .click();
    await page.getByLabel('Choose files to attach').setInputFiles({
      name: 'attendance.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'),
    });
    await expect(page.getByRole('link', { name: 'attendance.pdf' })).toBeVisible();
    await page.keyboard.press('Escape');
    await page.getByRole('button', { name: 'Submit report' }).click();
    await expect(page.getByText(/submitted/i).first()).toBeVisible();

    const chief = await browser.newPage();
    chief.on('dialog', (d) => d.accept());
    await signIn(chief, admin);
    await chief.goto(`/submissions?fy=${fyId}&period=${jan.id}`);
    await expect(
      chief.getByRole('row', { name: /PME/ }).getByText('Done', { exact: true }),
    ).toBeVisible();
    await chief.getByRole('button', { name: /^Close / }).click();
    await expect(chief.getByText(/is closed/).first()).toBeVisible();
    await chief.goto(`/dashboard?fy=${fyId}&period=${jan.id}`);
    await expect(chief.getByText('FINAL', { exact: true })).toBeVisible();
    await chief.close();
    const feb = periods.find((p) => p.month_index === 2)!;
    saveState({ code, admin, officeAdmin, viewer, fyId, janId: jan.id, febId: feb.id });
    expect(lineages.length).toBe(3);
  });

  test('4. monitoring', async ({ page }) => {
    const jan = periods.find((p) => p.month_index === 1)!;
    await signIn(page, viewer);
    await page.goto(`/dashboard?fy=${fyId}&period=${jan.id}`);
    await expect(page.getByRole('heading', { name: 'Department of Smoke' })).toBeVisible();
    await expect(
      page.getByRole('img', { name: 'Progress to date: actual and planned history' }),
    ).toBeVisible();
    await page.goto(`/rankings?fy=${fyId}&period=${jan.id}`);
    await expect(page.getByRole('heading', { name: 'Rankings' })).toBeVisible();
    await page.goto(`/dashboard?fy=${fyId}&period=${jan.id}`);
    await page.getByRole('button', { name: /PME/ }).first().click();
    await expect(page.getByRole('heading', { name: 'Planning and Monitoring' })).toBeVisible();
    await page.getByRole('tab', { name: 'Activities' }).click();
    await page.getByRole('button', { name: /^A Training courses/ }).click();
    await expect(
      page.getByRole('dialog').getByRole('link', { name: 'attendance.pdf' }),
    ).toBeVisible();
  });

  test('5. reporting', async ({ page }) => {
    const jan = periods.find((p) => p.month_index === 1)!;
    await signIn(page, admin);
    await page.goto(`/dashboard?fy=${fyId}&period=${jan.id}`);
    for (const [format, ext] of [
      ['Excel workbook', 'xlsx'],
      ['PowerPoint presentation for the month', 'pptx'],
      ['Over-all performance for the year', 'pptx'],
    ] as const) {
      await page.getByRole('button', { name: 'Export' }).click();
      const dialog = page.getByRole('dialog', { name: 'Export' });
      await dialog.getByLabel(new RegExp(format)).check();
      await dialog.getByLabel('The whole agency').check();
      await dialog.getByRole('button', { name: /Prepare/ }).click();
      const link = dialog.getByRole('link', { name: /^Download / });
      await expect(link).toBeVisible({ timeout: 45_000 });
      const [download] = await Promise.all([page.waitForEvent('download'), link.click()]);
      expect(download.suggestedFilename()).toMatch(new RegExp(`\\.${ext}$`));
      await page.keyboard.press('Escape');
    }
    await page.goto('/exports');
    await expect(page.getByRole('link', { name: /-overall\.pptx$/ })).toBeVisible();
  });
});

test.describe.serial('phone: following results on the agency set up on desktop', () => {
  let state: State | null = null;
  // eslint-disable-next-line no-empty-pattern -- Playwright needs the fixtures argument destructured
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== 'phone', 'phone viewport only');
    state = loadState();
    test.skip(!state, 'run the desktop flows first');
  });

  test('1–3 on a phone: editing screens send people to a computer; a photo can be attached', async ({
    page,
  }) => {
    const s = state!;
    await signIn(page, s.officeAdmin);
    for (const path of ['/structure', '/users', `/reports?fy=${s.fyId}`, '/plans/any']) {
      await page.goto(path);
      await expect(page.getByRole('heading', { name: 'Open on a computer to edit' })).toBeVisible();
      await expectNoHorizontalScroll(page);
    }
    await page.goto(`/dashboard?fy=${s.fyId}&period=${s.febId}`);
    await expectNoHorizontalScroll(page);
    await page.getByRole('tab', { name: 'Activities' }).click();
    await page.getByRole('button', { name: /^B Manuals/ }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Take a photo for February').setInputFiles({
      name: 'IMG_0001.png',
      mimeType: 'image/png',
      buffer: Buffer.concat([
        Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
        Buffer.alloc(32),
      ]),
    });
    await expect(dialog.getByRole('link', { name: 'IMG_0001.png' })).toBeVisible();
    await expectNoHorizontalScroll(page);
  });

  test('4. monitoring on a phone', async ({ page }) => {
    const s = state!;
    await signIn(page, s.viewer);
    await page.goto(`/dashboard?fy=${s.fyId}&period=${s.janId}`);
    await expect(page.getByText('FINAL', { exact: true })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await page.goto(`/rankings?fy=${s.fyId}&period=${s.janId}`);
    await expect(page.getByRole('heading', { name: 'Rankings' })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await page.goto('/notifications');
    await expectNoHorizontalScroll(page);
    await page.goto('/help');
    await expectNoHorizontalScroll(page);
  });

  test('5. reporting on a phone', async ({ page }) => {
    const s = state!;
    await signIn(page, s.admin);
    await page.goto(`/dashboard?fy=${s.fyId}&period=${s.janId}`);
    await page.getByRole('button', { name: 'Export' }).click();
    const dialog = page.getByRole('dialog', { name: 'Export' });
    await dialog.getByRole('button', { name: /Prepare/ }).click();
    const link = dialog.getByRole('link', { name: /^Download / });
    await expect(link).toBeVisible({ timeout: 45_000 });
    const [download] = await Promise.all([page.waitForEvent('download'), link.click()]);
    expect(download.suggestedFilename()).toMatch(/\.xlsx$/);
    await expectNoHorizontalScroll(page);
  });
});
