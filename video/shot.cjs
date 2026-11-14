// node shot.cjs t1 t2 ... -> /tmp/vs-<t>.png (single frames for quick checks)
const { chromium } = require('/Users/snowball/.npm/_npx/31e32ef8478fbf80/node_modules/playwright-core');
(async () => {
  const b = await chromium.launch({ channel: 'chrome', args: ['--use-angle=metal', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  p.on('pageerror', (e) => console.error('pageerror:', e.message));
  await p.goto('http://localhost:8765/index.html'); await p.waitForFunction(() => window.ready === true); await p.evaluate(() => document.fonts.ready);
  for (const t of process.argv.slice(2)) { await p.evaluate((t) => window.render(t), Number(t)); await p.screenshot({ path: '/tmp/vs-' + t + '.png' }); }
  await b.close();
})();
