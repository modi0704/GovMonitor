import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { officeId, openApp } from './helpers';

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

test('the main pages', async ({ page }, info) => {
  // P13.1: the content security policy must never block anything the app itself uses.
  const blocked: string[] = [];
  page.on('console', (m) => {
    if (/Content Security Policy|Refused to/.test(m.text())) blocked.push(m.text());
  });
  await openApp(page);
  await audit(page, 'step-by-step');
  await page.goto('/dashboard');
  await audit(page, 'dashboard');
  const rdi = await officeId(page, 'RDI');
  // The demo year (the smoke flows may have added a later one).
  const years = (await page.evaluate(() =>
    fetch('/api/v1/fiscal-years').then((r) => r.json()),
  )) as { id: string; label: string }[];
  const fy = years.find((y) => y.label === '2023')!.id;
  await page.goto(`/dashboard?fy=${fy}&office=${rdi}`);
  await page.getByRole('tab', { name: 'Activities' }).click();
  await audit(page, 'activities');
  await page.goto('/rankings');
  await audit(page, 'rankings');
  await page.goto('/user-guide');
  await audit(page, 'user-guide');
  await page.goto('/exports');
  await audit(page, 'exports');
  if (info.project.name === 'desktop') {
    for (const path of ['/reports', '/plans', '/fiscal-years', '/structure']) {
      await page.goto(path);
      await audit(page, path);
    }
  }
  expect(blocked, blocked.join('\n')).toEqual([]);
});
