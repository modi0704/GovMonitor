import { expect, type Page } from '@playwright/test';

export const ADMIN = {
  email: 'admin@sample-ministry.demo',
  password: process.env.DEMO_PASSWORD ?? 'demo-password-2026',
};

export async function signIn(page: Page, who = ADMIN) {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill(who.email);
  await page.getByLabel('Password').fill(who.password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

export async function officeId(page: Page, code: string): Promise<string> {
  const offices = (await page.evaluate(() => fetch('/api/v1/offices').then((r) => r.json()))) as {
    id: string;
    code: string;
  }[];
  const found = offices.find((o) => o.code === code);
  if (!found) throw new Error(`no office ${code}`);
  return found.id;
}

/** The page must never scroll sideways (Phase 12 exit check: 360 px). */
export async function expectNoHorizontalScroll(page: Page) {
  const { scroll, width } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    width: window.innerWidth,
  }));
  expect(scroll, 'page is wider than the screen').toBeLessThanOrEqual(width);
}
