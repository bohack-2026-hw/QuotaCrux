// node export.cjs <base-url> <out-dir>
// Writes <out-dir>/QuotaCrux.pdf (vector), and for build_pptx.py: <out-dir>/build/bg-NN.png (each slide with its text hidden)
// plus <out-dir>/build/deck.json (every text block with position, style and runs, and the speaker notes).
const fs = require('fs')
const path = require('path')
const { chromium } = require(process.env.PLAYWRIGHT_CORE || '/Users/snowball/.npm/_npx/31e32ef8478fbf80/node_modules/playwright-core')

const [base, outDir] = [process.argv[2] || 'http://localhost:8766/docs/presentation/slides/index.html', process.argv[3] || '.']
const build = path.join(outDir, 'build')

;(async () => {
  fs.mkdirSync(build, { recursive: true })
  const b = await chromium.launch({ channel: 'chrome' })
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 })
  p.on('pageerror', (e) => console.error('pageerror:', e.message))
  await p.goto(base)
  await p.waitForFunction(() => window.deckReady === true)
  await p.evaluate(() => document.fonts.ready)
  await p.waitForLoadState('networkidle')
  await p.pdf({ path: path.join(outDir, 'QuotaCrux.pdf'), width: '1920px', height: '1080px', printBackground: true })
  await p.addStyleTag({ content: '.__hide, .__hide * { color: transparent !important; -webkit-text-fill-color: transparent !important; text-shadow: none !important; }' })

  const n = await p.evaluate(() => document.querySelectorAll('.slide').length)
  const deck = []
  for (let i = 0; i < n; i++) {
    const info = await p.evaluate((i) => {
      const slide = document.querySelectorAll('.slide')[i]
      const sr = slide.getBoundingClientRect()
      const isInline = (el) => getComputedStyle(el).display === 'inline'
      const visible = (el) => { for (let e = el; e && e !== slide; e = e.parentElement) { const cs = getComputedStyle(e); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) return false } return true }
      // a text block is the nearest non-inline ancestor of a text node (outside SVG)
      const blocks = []
      const walker = document.createTreeWalker(slide, NodeFilter.SHOW_TEXT)
      for (let t = walker.nextNode(); t; t = walker.nextNode()) {
        if (!t.nodeValue.trim() || t.parentElement.closest('svg')) continue
        let el = t.parentElement
        while (el !== slide && isInline(el)) el = el.parentElement
        if (!blocks.includes(el) && visible(el)) blocks.push(el)
      }
      const out = blocks.map((blk) => {
        const cs = getComputedStyle(blk)
        const pre = cs.whiteSpace.startsWith('pre')
        const runs = []
        const style = (el) => { const s = getComputedStyle(el); return { color: s.color, size: parseFloat(s.fontSize), weight: +s.fontWeight || 400, family: s.fontFamily, ls: s.letterSpacing === 'normal' ? 0 : parseFloat(s.letterSpacing) } }
        const walk = (node) => {
          for (const c of node.childNodes) {
            if (c.nodeType === 3) { let s = c.nodeValue; if (!pre) s = s.replace(/\s+/g, ' '); if (s) runs.push({ text: s, ...style(c.parentElement) }) }
            else if (c.nodeType === 1) {
              if (c.tagName === 'BR') runs.push({ text: '\n' })
              else if (c.closest('svg') || c.tagName === 'IMG') continue
              else if (isInline(c)) walk(c)
            }
          }
        }
        walk(blk)
        if (!pre) { // trim block edges like CSS does
          while (runs.length && runs[0].text !== '\n' && !runs[0].text.trim()) runs.shift()
          if (runs.length && runs[0].text !== '\n') runs[0].text = runs[0].text.replace(/^\s+/, '')
          const last = runs[runs.length - 1]; if (last && last.text !== '\n') last.text = last.text.replace(/\s+$/, '')
        }
        const r = blk.getBoundingClientRect()
        const pl = parseFloat(cs.paddingLeft), pr = parseFloat(cs.paddingRight), pt = parseFloat(cs.paddingTop), pb = parseFloat(cs.paddingBottom)
        const lh = cs.lineHeight === 'normal' ? parseFloat(cs.fontSize) * 1.32 : parseFloat(cs.lineHeight)
        // the text box covers the content box; flex/grid centring is already reflected in the element's own rect
        let align = cs.textAlign; if (align === 'start') align = 'left'; if (align === 'end') align = 'right'
        if (cs.display.includes('flex') && cs.justifyContent === 'center') align = 'center'
        return { x: r.left - sr.left + pl, y: r.top - sr.top + pt, w: r.width - pl - pr, h: r.height - pt - pb, lh, align, pre,
          valign: cs.display.includes('flex') && cs.alignItems === 'center' ? 'middle' : 'top', runs }
      }).filter((b) => b.runs.some((r) => r.text.trim()) && b.w > 2)
      blocks.forEach((el) => el.classList.add('__hide'))
      slide.scrollIntoView()
      return { blocks: out, notes: slide.dataset.notes || '' }
    }, i)
    const el = (await p.$$('.slide'))[i]
    const bg = path.join(build, `bg-${String(i + 1).padStart(2, '0')}.png`)
    await el.screenshot({ path: bg })
    await p.evaluate(() => document.querySelectorAll('.__hide').forEach((e) => e.classList.remove('__hide')))
    deck.push({ bg: path.basename(bg), ...info })
    process.stdout.write(`slide ${i + 1}/${n}: ${info.blocks.length} text blocks\n`)
  }
  fs.writeFileSync(path.join(build, 'deck.json'), JSON.stringify(deck))
  await b.close()
})()
