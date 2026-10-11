// Renders the film: 240 subframes/s captured with Playwright, blended 4:1 with ffmpeg tmix -> 60 fps.
// usage: node render.mjs <outdir> [workers=3] [fps=60] [sub=4]
import { chromium } from 'playwright';
import { spawn } from 'child_process';
import fs from 'fs';
const outdir = process.argv[2] || 'out';
const WORKERS = +(process.argv[3] || 3), FPS = +(process.argv[4] || 60), SUB = +(process.argv[5] || 4);
fs.mkdirSync(outdir, { recursive: true });
const DUR = 30, NF = DUR * FPS;
const F0 = +(process.argv[6] || 0), F1 = +(process.argv[7] || NF), TAG = process.argv[8] || 'chunk';
const per = Math.ceil((F1 - F0) / WORKERS);
const t0 = Date.now();
async function worker(w) {
  const f0 = F0 + w * per, f1 = Math.min(F1, f0 + per);
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1440 } });
  page.on('pageerror', e => console.log(`[w${w} pageerror]`, e.message));
  await page.goto('http://127.0.0.1:8765/index.html');
  await page.evaluate(() => window.ready);
  await page.addStyleTag({ content: '#out{width:1440px!important;height:1440px!important}' });
  const cv = await page.$('#out');
  const vf = SUB > 1 ? `tmix=frames=${SUB},select='eq(mod(n\\,${SUB})\\,${SUB - 1})',setpts=N/${FPS}/TB` : `setpts=N/${FPS}/TB`;
  const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS * SUB), '-c:v', 'png', '-i', '-',
    '-vf', vf, '-r', String(FPS), '-c:v', 'libx264', '-preset', 'medium', '-crf', '9', '-pix_fmt', 'yuv444p', `${outdir}/${TAG}${w}.mp4`], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let f = f0; f < f1; f++) {
    for (let s = 0; s < SUB; s++) {
      const t = (f * SUB + s) / (FPS * SUB);
      await page.evaluate(t => window.seek(t), t);
      const buf = await cv.screenshot({ type: 'png' });
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    }
    if (f % 60 === 0) console.log(`w${w} frame ${f}/${f1} ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close();
}
await Promise.all([...Array(WORKERS).keys()].map(worker));
fs.writeFileSync(`${outdir}/${TAG}_list.txt`, [...Array(WORKERS).keys()].map(w => `file '${TAG}${w}.mp4'`).join('\n'));
console.log('done', ((Date.now() - t0) / 1000).toFixed(0), 's');
