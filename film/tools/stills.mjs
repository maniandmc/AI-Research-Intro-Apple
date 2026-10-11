// usage: node stills.mjs outdir t1 t2 ...   (needs a static server on :8765 serving film/)
import { chromium } from 'playwright';
import fs from 'fs';
const [outdir, ...ts] = process.argv.slice(2);
fs.mkdirSync(outdir, { recursive: true });
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 1440 } });
page.on('console', m => console.log('[page]', m.type(), m.text()));
page.on('pageerror', e => console.log('[pageerror]', e.message));
await page.goto('http://127.0.0.1:8765/index.html');
await page.evaluate(() => window.ready);
const cv = await page.$('#out');
await page.addStyleTag({ content: '#out{width:1440px!important;height:1440px!important}' });
for (const t of ts) {
  const t0 = Date.now();
  await page.evaluate(t => window.seek(t), parseFloat(t));
  const dt = Date.now() - t0;
  const t1 = Date.now();
  await cv.screenshot({ path: `${outdir}/t${parseFloat(t).toFixed(2)}.png` });
  console.log('t', t, 'seek ms', dt, 'shot ms', Date.now() - t1);
}
await browser.close();
