import { expect, test, type Page } from '@playwright/test';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expectNoHorizontalScroll, openApp } from './helpers';

/**
 * P12.7, D49 — smoke tests of the single officer's routine, as the app ships: no sign-in, one
 * person entering every office's figures.
 *
 * Desktop works on two new offices and a new year inside the demo agency (a future year not used
 * yet and stamped codes, so repeated runs never collide): offices → year → plans (Save as final,
 * Change plan) → monthly results (Mark as done, Change results) → close the month → dashboard,
 * rankings → downloads; then the six steps of Step-by-step and the removed pages. The phone project
 * uses that year for what a phone is for (D12): following results, attaching a photo,
 * downloading an export — and checks that editing screens say to use a computer and that no page
 * scrolls sideways.
 *
 * Needs a running server (shipped defaults, LOGIN_DISABLED on) with the demo data and a worker
 * (exports). SMOKE_BASE_URL points at it.
 */

// Outside test-results/, which Playwright empties at the start of every run.
const STATE_FILE = join(tmpdir(), 'govmonitor-smoke-state.json');

interface State {
  fyId: string;
  janId: string;
  febId: string;
  planId: string;
  officeId: string;
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

interface OfficeRow {
  id: string;
  code: string;
  name: string;
  parent_id: string | null;
}

test.describe.serial('desktop: the monitoring routine', () => {
  // eslint-disable-next-line no-empty-pattern -- Playwright needs the fixtures argument destructured
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== 'desktop', 'set-up and planning are desktop work (D12)');
  });
  const stamp = Date.now().toString(36).toUpperCase().slice(-5);
  const codeA = `SA${stamp}`;
  const codeB = `SB${stamp}`;
  let startYear = 0;
  let fyId = '';
  let periods: { id: string; month_index: number }[] = [];
  let planId = '';
  let officeA = '';

  test('1. offices: add two, delete one', async ({ page }) => {
    page.on('dialog', (d) => d.accept());
    await openApp(page);
    // No sign-in, no account menu, no removed menu items.
    await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0);
    for (const gone of ['Users', 'Plans to approve', 'Who has reported', 'Notifications']) {
      await expect(page.getByRole('link', { name: gone, exact: true })).toHaveCount(0);
    }
    const offices = await api<OfficeRow[]>(page, 'GET', 'offices');
    const top = offices.find((o) => o.parent_id === null)!;
    for (const [code, name] of [
      [codeA, `Smoke office ${stamp}`],
      [codeB, `Smoke spare ${stamp}`],
    ]) {
      await api(page, 'POST', 'offices', { parent_id: top.id, code, name });
    }
    await page.goto('/structure');
    await page.getByRole('treeitem', { name: new RegExp(codeB) }).click();
    await page.getByRole('button', { name: 'Delete', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('checkbox').check();
    await dialog.getByRole('button', { name: 'Delete permanently' }).click();
    await expect(page.getByRole('treeitem', { name: new RegExp(codeB) })).toHaveCount(0);
    await expect(page.getByRole('treeitem', { name: new RegExp(codeA) })).toBeVisible();
    officeA = (await api<OfficeRow[]>(page, 'GET', 'offices')).find((o) => o.code === codeA)!.id;
  });

  test('2. year: create and open, scored the Excel way', async ({ page }) => {
    page.on('dialog', (d) => d.accept());
    await openApp(page);
    const used = (await api<{ start_date: string }[]>(page, 'GET', 'fiscal-years')).map((y) =>
      Number(y.start_date.slice(0, 4)),
    );
    startYear = 2099;
    while (used.includes(startYear)) startYear -= 1;
    await page.goto('/fiscal-years');
    await page.getByRole('button', { name: 'New fiscal year' }).click();
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByText('Scoring method')).toHaveCount(0);
    await dialog.getByLabel('Label').fill(`Smoke ${startYear}`);
    await dialog.getByLabel('Starts in the year').fill(String(startYear));
    await dialog.getByRole('button', { name: 'Create' }).click();
    const row = page.getByRole('row', { name: new RegExp(`Smoke ${startYear}`) });
    await row.getByRole('button', { name: 'Open', exact: true }).click();
    await expect(row.getByText('open', { exact: true })).toBeVisible();
    const years = await api<{ id: string; label: string; preset: string }[]>(
      page,
      'GET',
      'fiscal-years',
    );
    const fy = years.find((y) => y.label === `Smoke ${startYear}`)!;
    expect(fy.preset).toBe('workbook_compatible');
    fyId = fy.id;
    periods = (
      await api<{ periods: { id: string; month_index: number }[] }>(
        page,
        'GET',
        `fiscal-years/${fyId}`,
      )
    ).periods;
  });

  test('3. plan: Save as final, then Change plan', async ({ page }) => {
    page.on('dialog', (d) => d.accept());
    await openApp(page);
    await page.goto(`/plans?fy=${fyId}`);
    await page
      .getByRole('row', { name: new RegExp(codeA) })
      .getByRole('button', { name: 'Start empty plan' })
      .click();
    await expect(page).toHaveURL(/\/plans\/[0-9a-f-]+$/);
    planId = page.url().split('/').pop()!;
    // Enter the plan (the grid sends this same request), with one mistake to fix.
    const rows = [
      { client_key: 'o', row_kind: 'output', code: 'O1', title: 'Services', sort_order: 0 },
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
    const saved = await api<{ plan: { rows: { id: string; code: string }[] } }>(
      page,
      'POST',
      `plans/${planId}/save`,
      { rows },
    );
    await page.reload();
    await page.getByRole('button', { name: 'Save as final' }).click();
    await expect(page.getByText(/add up to 3, not the annual target 4/).first()).toBeVisible();
    const b = saved.plan.rows.find((r) => r.code === 'B')!;
    await api(page, 'POST', `plans/${planId}/save`, {
      rows: [{ id: b.id, targets: ['0', '2', '2', ...Array(9).fill('0')] }],
    });
    await page.reload();
    await page.getByRole('button', { name: 'Save as final' }).click();
    await expect(page.getByText('Final — used for the monthly results')).toBeVisible();
    await expect(page.getByRole('button', { name: /Approve|Submit for approval/ })).toHaveCount(0);

    // Change plan: an editable copy opens; saving it as final replaces the old one.
    await page.getByRole('button', { name: 'Change plan' }).click();
    await expect(page).not.toHaveURL(new RegExp(planId));
    await page.getByRole('button', { name: 'Save as final' }).click();
    await expect(page.getByText('Final — used for the monthly results')).toBeVisible();
    planId = page.url().split('/').pop()!;
    await page.goto(`/plans?fy=${fyId}`);
    await expect(
      page.getByRole('row', { name: new RegExp(codeA) }).getByText('Final'),
    ).toBeVisible();
  });

  test('4. monthly results: mark as done, change, close the month', async ({ page }) => {
    page.on('dialog', (d) => d.accept());
    const jan = periods.find((p) => p.month_index === 1)!;
    await openApp(page);
    await page.goto(`/reports?fy=${fyId}&office=${officeA}&period=${jan.id}`);
    await expect(page.getByLabel('Show')).toHaveCount(0);
    await page.getByLabel('Done this month, A').fill('1'); // planned 2: behind
    await page.getByLabel('Reason for delay, A').fill('Venue not available');
    await page.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByRole('button', { name: 'Saved' })).toBeVisible();
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
    await page.getByRole('button', { name: 'Mark as done' }).click();
    await expect(page.getByText('Done', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Return for correction' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Change results' }).click();
    await expect(page.getByText('Not done yet')).toBeVisible();
    await page.getByRole('button', { name: 'Mark as done' }).click();
    await expect(page.getByText('Done', { exact: true })).toBeVisible();

    await page.goto(`/fiscal-years/${fyId}`);
    await page.getByRole('button', { name: 'Close month' }).click();
    await expect(page.getByText(/is closed\. Its figures are final/)).toBeVisible();
    await page.goto(`/dashboard?fy=${fyId}&period=${jan.id}`);
    await expect(page.getByText('FINAL', { exact: true })).toBeVisible();
    const feb = periods.find((p) => p.month_index === 2)!;
    saveState({ fyId, janId: jan.id, febId: feb.id, planId, officeId: officeA });
  });

  test('5. dashboard and rankings', async ({ page }) => {
    const jan = periods.find((p) => p.month_index === 1)!;
    await openApp(page);
    await page.goto(`/dashboard?fy=${fyId}&period=${jan.id}`);
    await expect(page.getByLabel('Scores of')).toHaveCount(0);
    await expect(
      page.getByRole('img', { name: 'Progress to date: actual and planned history' }),
    ).toBeVisible();
    await page
      .getByRole('button', { name: new RegExp(codeA) })
      .first()
      .click();
    await expect(page.getByRole('heading', { name: `Smoke office ${stamp}` })).toBeVisible();
    await page.getByRole('tab', { name: 'Activities' }).click();
    await page.getByRole('button', { name: /^A Training courses/ }).click();
    await expect(
      page.getByRole('dialog').getByRole('link', { name: 'attendance.pdf' }),
    ).toBeVisible();
    await page.goto(`/rankings?fy=${fyId}&period=${jan.id}`);
    await expect(page.getByRole('heading', { name: 'Rankings' })).toBeVisible();
  });

  test('6. downloads', async ({ page }) => {
    const jan = periods.find((p) => p.month_index === 1)!;
    await openApp(page);
    await page.goto(`/dashboard?fy=${fyId}&period=${jan.id}&office=${officeA}`);
    for (const [format, ext] of [
      ['Excel workbook', 'xlsx'],
      ['PowerPoint presentation for the month', 'pptx'],
      ['Over-all performance for the year', 'pptx'],
    ] as const) {
      await page.getByRole('button', { name: 'Export' }).click();
      const dialog = page.getByRole('dialog', { name: 'Export' });
      await dialog.getByLabel(new RegExp(format)).check();
      await expect(dialog.getByLabel('Scores of')).toHaveCount(0);
      await dialog.getByRole('button', { name: /Prepare/ }).click();
      const link = dialog.getByRole('link', { name: /^Download / });
      await expect(link).toBeVisible({ timeout: 45_000 });
      const [download] = await Promise.all([page.waitForEvent('download'), link.click()]);
      expect(download.suggestedFilename()).toMatch(new RegExp(`\\.${ext}$`));
      await page.keyboard.press('Escape');
    }
    await page.goto('/exports');
    await expect(page.getByRole('link', { name: /-overall\.pptx$/ }).first()).toBeVisible();
  });

  test('7. Step-by-step: all six steps open; removed pages are Not found', async ({ page }) => {
    await openApp(page);
    await page.goto(`/?fy=${fyId}`);
    await expect(page.getByRole('heading', { name: 'Step-by-step' })).toBeVisible();
    const steps = ['offices', 'year', 'plans', 'results', 'review', 'report'];
    for (const [i, step] of steps.entries()) {
      await page.goto(`/?fy=${fyId}&step=${step}`);
      await expect(
        page.getByRole('heading', { level: 2, name: new RegExp(`^Step ${i + 1}`) }),
      ).toBeVisible();
      await expect(page.getByText(/Waiting for approval|Needs changes/)).toHaveCount(0);
      for (const link of await page.locator('main a[href^="/"]').all()) {
        const href = (await link.getAttribute('href'))!.split('?')[0]!;
        expect(['/submissions', '/plans/approvals', '/groups', '/users']).not.toContain(href);
      }
    }
    for (const path of [
      '/users',
      '/account/security',
      '/plans/approvals',
      '/submissions',
      '/notifications',
      '/settings/alerts',
      '/groups',
      '/settings/report-template',
      '/help',
      '/audit',
      '/platform',
      '/platform/sign-in',
    ]) {
      await page.goto(path);
      await expect(page.getByRole('heading', { name: 'Page not found' }), path).toBeVisible();
    }
  });
});

test.describe.serial('phone: following results on the year set up on desktop', () => {
  let state: State | null = null;
  // eslint-disable-next-line no-empty-pattern -- Playwright needs the fixtures argument destructured
  test.beforeEach(({}, info) => {
    test.skip(info.project.name !== 'phone', 'phone viewport only');
    state = loadState();
    test.skip(!state, 'run the desktop flows first');
  });

  test('editing screens send people to a computer; a photo can be attached', async ({ page }) => {
    const s = state!;
    await openApp(page);
    for (const path of ['/structure', `/reports?fy=${s.fyId}`, `/plans/${s.planId}`]) {
      await page.goto(path);
      await expect(page.getByRole('heading', { name: 'Open on a computer to edit' })).toBeVisible();
      await expectNoHorizontalScroll(page);
    }
    await page.goto(`/dashboard?fy=${s.fyId}&period=${s.febId}&office=${s.officeId}`);
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

  test('monitoring on a phone', async ({ page }) => {
    const s = state!;
    await openApp(page);
    await page.goto(`/dashboard?fy=${s.fyId}&period=${s.janId}`);
    await expect(page.getByText('FINAL', { exact: true })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await page.goto(`/rankings?fy=${s.fyId}&period=${s.janId}`);
    await expect(page.getByRole('heading', { name: 'Rankings' })).toBeVisible();
    await expectNoHorizontalScroll(page);
    await page.goto('/user-guide');
    await expectNoHorizontalScroll(page);
  });

  test('downloads on a phone', async ({ page }) => {
    const s = state!;
    await openApp(page);
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
