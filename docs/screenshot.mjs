// One-off doc image generator. Reuses the playwright-core + real installed Chrome
// setup already proven in the Ember and Oak project's e2e check, run from there since
// this Python project doesn't carry a node dependency of its own for a one-time task.
import { chromium } from "playwright-core";
import path from "node:path";

const pairs = [
  ["cover.html", "cover.png", 1600, 900],
  ["erd-real.html", "erd-real.png", 1600, 900],
];

const docsDir = process.argv[2];
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage();

for (const [html, png, width, height] of pairs) {
  await page.setViewportSize({ width, height });
  await page.goto("file://" + path.join(docsDir, html));
  await page.screenshot({ path: path.join(docsDir, png) });
  console.log(`wrote ${png}`);
}

await browser.close();
