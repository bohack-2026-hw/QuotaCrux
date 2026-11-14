// node events.cjs out.json -> the sound cue list from window.sfxEvents()
const fs = require('fs')
const { chromium } = require('/Users/snowball/.npm/_npx/31e32ef8478fbf80/node_modules/playwright-core');
(async () => {
  const b = await chromium.launch({ channel: 'chrome' })
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } })
  await p.goto('http://localhost:8765/index.html'); await p.waitForFunction(() => window.ready === true)
  const ev = await p.evaluate(() => ({ duration: window.DURATION, events: window.sfxEvents() }))
  fs.writeFileSync(process.argv[2], JSON.stringify(ev.events))
  console.log(ev.events.length, 'cues', ev.duration, 's')
  await b.close()
})()
