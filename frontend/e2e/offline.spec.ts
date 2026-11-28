import { expect, test, type Page } from '@playwright/test';

/**
 * P13.7 — an office install with no internet: every page loads, exports work, and the browser
 * never asks for anything outside the site. Run by deploy/test-offline-install.sh (OFFLINE_CHECK=1)
 * against the demo data; skipped otherwise.
 */
test.skip(!process.env.OFFLINE_CHECK, 'run by deploy/test-offline-install.sh');
test.use({ ignoreHTTPSErrors: true });

const PAGES = [
  '/',
  '/dashboard',
  '/rankings',
  '/reports',
  '/plans',
  '/fiscal-years',
  '/structure',
  '/exports',
  '/user-guide',
];

test('every page and every export stays on the site', async ({ page, baseURL }, info) => {
  test.skip(info.project.name !== 'desktop', 'desktop run is enough here');
  test.setTimeout(240_000); // every page, then three exports that each wait for the worker
  const site = new URL(baseURL!).origin;
  const outside: string[] = [];
  const failed: string[] = [];
  page.on('request', (r) => {
    const url = r.url();
    if (!url.startsWith(site) && !url.startsWith('data:') && !url.startsWith('blob:'))
      outside.push(url);
  });
  page.on('requestfailed', (r) => failed.push(`${r.url()} ${r.failure()?.errorText}`));
  page.on('pageerror', (e) => failed.push(`page error: ${e.message}`));

  await page.goto('/sign-in');
  await page.getByLabel('Email').fill('admin@sample-ministry.demo');
  await page.getByLabel('Password').fill(process.env.DEMO_PASSWORD ?? 'demo-password-2026');
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();

  for (const path of PAGES) {
    await page.goto(path);
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
    await page.waitForLoadState('networkidle');
  }
  await exportFile(page, 'Excel workbook', 'xlsx');
  await exportFile(page, 'PowerPoint presentation for the month', 'pptx');
  await exportFile(page, 'Over-all performance for the year', 'pptx');

  expect(outside, `requests outside ${site}:\n${outside.join('\n')}`).toEqual([]);
  expect(
    failed.filter((f) => !f.includes('net::ERR_ABORTED')),
    failed.join('\n'),
  ).toEqual([]);
});

async function exportFile(page: Page, format: string, ext: string) {
  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Export' }).click();
  const dialog = page.getByRole('dialog', { name: 'Export' });
  await dialog.getByLabel(new RegExp(format)).check();
  await dialog.getByLabel('The whole agency').check();
  await dialog.getByRole('button', { name: /Prepare/ }).click();
  const link = dialog.getByRole('link', { name: /^Download / });
  await expect(link).toBeVisible({ timeout: 60_000 });
  const [download] = await Promise.all([page.waitForEvent('download'), link.click()]);
  expect(download.suggestedFilename()).toMatch(new RegExp(`\\.${ext}$`));
  await page.keyboard.press('Escape');
}
