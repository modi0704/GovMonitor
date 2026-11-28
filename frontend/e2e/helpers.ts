import { expect, type Page } from '@playwright/test';

/** D49: the app opens straight away — there is no sign-in as shipped. */
export async function openApp(page: Page, path = '/') {
  await page.goto(path);
  await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
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
