import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { officeId, signIn } from './helpers';

/** P12.5: automated WCAG 2.1 A/AA checks (contrast, labels, names, landmarks) on the main pages. */
async function audit(page: Page, name: string) {
  await page.waitForLoadState('networkidle');
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const problems = result.violations.map(
    (v) =>
      `${name}: ${v.id} (${v.impact}) ${v.help} → ${v.nodes
        .slice(0, 3)
        .map((n) => n.target.join(' '))
        .join(' | ')}`,
  );
  expect(problems, problems.join('\n')).toEqual([]);
}

test('sign-in page', async ({ page }) => {
  await page.goto('/sign-in');
  await audit(page, 'sign-in');
});

test('pages after sign-in', async ({ page }, info) => {
  // P13.1: the content security policy must never block anything the app itself uses.
  const blocked: string[] = [];
  page.on('console', (m) => {
    if (/Content Security Policy|Refused to/.test(m.text())) blocked.push(m.text());
  });
  await signIn(page);
  await audit(page, 'dashboard');
  const rdi = await officeId(page, 'RDI');
  await page.goto(`/dashboard?office=${rdi}`);
  await page.getByRole('tab', { name: 'Activities' }).click();
  await audit(page, 'activities');
  await page.goto('/rankings');
  await audit(page, 'rankings');
  await page.goto('/notifications');
  await audit(page, 'notifications');
  await page.goto('/exports');
  await audit(page, 'exports');
  if (info.project.name === 'desktop') {
    for (const path of [
      '/reports',
      '/plans',
      '/plans/approvals',
      '/submissions',
      '/fiscal-years',
      '/structure',
      '/users',
      '/audit',
      '/settings/alerts',
      '/settings/report-template',
      '/account/security',
    ]) {
      await page.goto(path);
      await audit(page, path);
    }
  }
  expect(blocked, blocked.join('\n')).toEqual([]);
});
