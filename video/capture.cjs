// Frame capture: node capture.cjs <fps> <from_s> <to_s> <out.mp4>  — pipes PNG frames into ffmpeg.
const { chromium } = require('/Users/snowball/.npm/_npx/31e32ef8478fbf80/node_modules/playwright-core');
const { spawn } = require('child_process');
(async () => {
  const [fps, from, to, out] = [Number(process.argv[2] || 30), Number(process.argv[3] || 0), Number(process.argv[4] || 15), process.argv[5] || 'out/sample.mp4'];
  const b = await chromium.launch({ channel: 'chrome', args: ['--use-angle=metal', '--enable-gpu-rasterization', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  p.on('console', (m) => { if (m.type() === 'error') console.error('page:', m.text()); });
  p.on('pageerror', (e) => console.error('pageerror:', e.message));
  await p.goto('http://localhost:8765/index.html');
  await p.waitForFunction(() => window.ready === true, null, { timeout: 60000 });
  await p.evaluate(() => document.fonts.ready);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-i', '-', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const n = Math.round((to - from) * fps);
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    await p.evaluate((t) => window.render(t), from + i / fps);
    const buf = await p.screenshot({ type: 'png' });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 90 === 0) console.log('frame', i, '/', n, ((Date.now() - t0) / 1000).toFixed(0) + 's');
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  await b.close();
  console.log('wrote', out);
})();
