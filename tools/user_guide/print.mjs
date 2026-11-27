// Prints an HTML file to an A4 PDF with page numbers, using the frontend's Playwright Chromium.
// Usage (from frontend/): node ../tools/user_guide/print.mjs <in.html> <out.pdf>
import { createRequire } from 'node:module';
import path from 'node:path';

// Resolve Playwright from the frontend's dependencies (the script runs with frontend/ as cwd).
const { chromium } = createRequire(path.resolve('package.json'))('@playwright/test');

const [src, out] = process.argv.slice(2);
const browser = await chromium.launch(
  process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {},
);
const page = await browser.newPage();
await page.goto(`file://${path.resolve(src)}`, { waitUntil: 'load' });
await page.pdf({
  path: out,
  format: 'A4',
  printBackground: true,
  displayHeaderFooter: true,
  headerTemplate: '<span></span>',
  footerTemplate:
    '<div style="font-size:8px;width:100%;text-align:center;color:#657068">GovMonitor · page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
  margin: { top: '16mm', bottom: '18mm', left: '14mm', right: '14mm' },
});
await browser.close();
