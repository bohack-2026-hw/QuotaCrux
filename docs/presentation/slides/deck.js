// Slide chrome and every diagram/chart in the deck (inline SVG). Numbers mirror the sources named in each slide footer.
const ACC = '#FF5A1F', ACC2 = '#FF9466', SLATE = '#7F8DA6', INK = '#EEEBE4', INK2 = '#A6A39C', INK3 = '#66645F'
const PANEL = '#15161A', PANEL2 = '#1C1D22', LINE = 'rgba(255,255,255,0.10)', LINE2 = 'rgba(255,255,255,0.22)'
const SANS = 'PingFang SC, sans-serif', NUM = 'Avenir Next, PingFang SC, sans-serif', MONO = 'Menlo, monospace'
const $ = (id) => document.getElementById(id)
const fmt = (n) => n.toLocaleString('en-US')

// ---------- svg helpers ----------
const attrs = (o) => Object.entries(o).map(([k, v]) => `${k.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase())}="${v}"`).join(' ')
const text = (x, y, s, o = {}) => `<text ${attrs({ x, y, fill: INK, fontFamily: SANS, fontSize: 24, ...o })}>${s}</text>`
const rect = (x, y, w, h, o = {}) => `<rect ${attrs({ x, y, width: w, height: h, rx: 12, fill: PANEL, stroke: LINE, ...o })}/>`
const line = (x1, y1, x2, y2, o = {}) => `<line ${attrs({ x1, y1, x2, y2, stroke: LINE2, strokeWidth: 2, ...o })}/>`
const path = (d, o = {}) => `<path ${attrs({ d, fill: 'none', stroke: LINE2, strokeWidth: 2, ...o })}/>`
const DEFS = `<defs>
  <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="${INK2}"/></marker>
  <marker id="arA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="${ACC}"/></marker>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="glow2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="18"/></filter>
  <linearGradient id="fadeA" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${ACC}" stop-opacity="0.35"/><stop offset="1" stop-color="${ACC}" stop-opacity="0"/></linearGradient>
  <linearGradient id="barA" x1="0" x2="1"><stop offset="0" stop-color="#C93E10"/><stop offset="1" stop-color="${ACC}"/></linearGradient>
  <linearGradient id="barS" x1="0" x2="1"><stop offset="0" stop-color="#4A5367"/><stop offset="1" stop-color="${SLATE}"/></linearGradient>
</defs>`
const svg = (id, body) => { const el = $(id); if (el) el.innerHTML = DEFS + body }
const arrow = (x1, y1, x2, y2, hot) => line(x1, y1, x2, y2, { stroke: hot ? ACC : INK2, markerEnd: `url(#${hot ? 'arA' : 'ar'})` })
const node = (x, y, w, h, title, sub, o = {}) => rect(x, y, w, h, { fill: o.fill || PANEL, stroke: o.hot ? ACC : LINE2, strokeWidth: o.hot ? 2.5 : 1.5 })
  + text(x + w / 2, y + (sub ? h / 2 - 4 : h / 2 + 9), title, { textAnchor: 'middle', fontSize: o.fs || 26, fontWeight: 700, fill: o.hot ? ACC2 : INK })
  + (sub ? text(x + w / 2, y + h / 2 + 28, sub, { textAnchor: 'middle', fontSize: o.ss || 19, fill: INK2, fontFamily: o.subMono ? MONO : SANS }) : '')

// ---------- chrome ----------
const slides = [...document.querySelectorAll('.slide')]
slides.forEach((s, i) => {
  const hd = document.createElement('div'); hd.className = 'hd'
  const k = s.dataset.kicker || ''
  const m = k.match(/^(\S+)\s·\s(.*)$/)
  hd.innerHTML = `<div class="k">${m ? `<b>${m[1]}</b>${m[2]}` : k}</div><div class="r"><span>QuotaCrux 枢决</span><i></i><span>${String(i + 1).padStart(2, '0')} / ${slides.length}</span></div>`
  s.prepend(hd)
  if (s.dataset.src) { const ft = document.createElement('div'); ft.className = 'ft'; ft.innerHTML = `<div class="src">来源　${s.dataset.src}</div>`; s.appendChild(ft) }
})

// ---------- cover art: a glowing step line over faint box stacks ----------
{
  let g = ''
  const heights = [9, 14, 6, 17, 11, 20, 8, 13]
  heights.forEach((h, i) => { for (let j = 0; j < h; j++) g += rect(1160 + i * 92, 1000 - (j + 1) * 34, 84, 30, { rx: 4, fill: 'rgba(255,255,255,0.025)', stroke: 'rgba(255,255,255,0.06)', strokeWidth: 1 }) })
  const pts = [[1180, 940], [1330, 940], [1330, 700], [1520, 700], [1520, 600], [1680, 600], [1680, 585], [1800, 585], [1800, 540], [1960, 540]]
  const d = 'M' + pts.map((p) => p.join(' ')).join(' L')
  g += path(d + ' L1960 1080 L1180 1080 Z', { fill: 'url(#fadeA)', stroke: 'none', opacity: 0.5 })
  g += path(d, { stroke: ACC, strokeWidth: 10, filter: 'url(#glow2)', opacity: 0.8 })
  g += path(d, { stroke: ACC, strokeWidth: 4 })
  ;[[1330, 700], [1520, 600], [1680, 585], [1800, 540]].forEach(([x, y]) => { g += `<circle cx="${x}" cy="${y}" r="9" fill="${ACC}" stroke="#0C0D0F" stroke-width="4"/>` })
  svg('coverArt', g)
}

// ---------- architecture ----------
{
  let g = ''
  // left inputs
  g += node(0, 40, 300, 110, '冻结任务包', '契约 · c0 · 开发 / final', {})
  g += node(0, 200, 300, 110, '经验快照 vN', '不可变 · 已验证程序', {})
  g += node(380, 120, 300, 110, '模型前复验', '≤ 3 个最相近程序', {})
  g += arrow(300, 95, 380, 155); g += arrow(300, 255, 380, 195)
  g += node(380, 330, 300, 110, '经验覆盖分流器', '相近成功 → 小 · 新族 → 大', { hot: true })
  g += arrow(530, 230, 530, 330)
  g += text(548, 290, '未达标', { fontSize: 19, fill: INK2 })
  // loop
  const LX = 770, LY = 20, LW = 720, LH = 560
  g += rect(LX, LY, LW, LH, { rx: 22, fill: 'rgba(255,90,31,0.035)', stroke: 'rgba(255,90,31,0.45)', strokeDasharray: '10 8', strokeWidth: 2 })
  g += text(LX + 28, LY + 46, '受预算约束的研究循环', { fontSize: 26, fontWeight: 700, fill: ACC2 })
  g += text(LX + LW - 28, LY + 46, '360 s · 20 req · 10 cand', { fontSize: 19, fill: INK2, fontFamily: MONO, textAnchor: 'end' })
  g += node(LX + 40, LY + 80, 300, 100, '可见状态', '契约 · 候选 · 裁判事实 · 预算', { ss: 17 })
  g += node(LX + 400, LY + 80, 280, 100, 'ActionRouter', 'llm | decisions', { hot: true, subMono: true })
  g += node(LX + 400, LY + 240, 280, 100, 'ModelRouter', 'rule | decisions', { hot: true, subMono: true })
  g += node(LX + 40, LY + 240, 300, 100, '生成', 'Qwen 小模型 · gpt-6.1-sol', { ss: 17 })
  g += node(LX + 40, LY + 410, 300, 110, '静态检查', '动作参数 · 允许范围', {})
  g += node(LX + 400, LY + 410, 280, 110, '隔离沙箱裁判', '正确性 · 规则用例 · 交替计时', { hot: true, ss: 17 })
  g += arrow(LX + 340, LY + 130, LX + 400, LY + 130)
  g += arrow(LX + 540, LY + 180, LX + 540, LY + 240); g += text(LX + 556, LY + 218, '分析 / 提出候选', { fontSize: 17, fill: INK2 })
  g += arrow(LX + 400, LY + 290, LX + 340, LY + 290)
  g += arrow(LX + 190, LY + 340, LX + 190, LY + 410)
  g += arrow(LX + 340, LY + 465, LX + 400, LY + 465)
  g += path(`M${LX + 680} ${LY + 130} H${LX + 705} V${LY + 465} H${LX + 680}`, { stroke: INK2, markerEnd: 'url(#ar)' })
  g += text(LX + 712, LY + 300, '取证 / 复验 / 结束', { fontSize: 17, fill: INK2, transform: `rotate(90 ${LX + 712} ${LY + 300})`, textAnchor: 'middle' })
  g += path(`M${LX + 400} ${LY + 500} H${LX + 20} V${LY + 130} H${LX + 40}`, { stroke: ACC, strokeDasharray: '6 6', markerEnd: 'url(#arA)' })
  g += text(LX + 30, LY + 560 - 18, '仅严格优于当前最佳才更新', { fontSize: 18, fill: ACC2 })
  g += arrow(680, 385, LX, 385)
  // outputs
  g += node(1560, 140, 168, 120, '冻结最佳', '隐藏 final 一次', { fs: 24, ss: 17 })
  g += node(1560, 330, 168, 120, '报告 · 账本', '复现包', { fs: 24, ss: 17 })
  g += node(1560, 520, 168, 120, '快照 vN+1', '原子发布', { hot: true, fs: 24, ss: 17 })
  g += arrow(LX + LW, 200, 1560, 200); g += arrow(1644, 260, 1644, 330); g += arrow(1644, 450, 1644, 520)
  g += path(`M680 175 C 720 175, 720 -10, 1100 -10 S 1560 60, 1600 140`, { stroke: INK3, strokeDasharray: '6 6', markerEnd: 'url(#ar)' })
  g += text(1150, 12, '复验达标 → 直接交付，不调用模型', { fontSize: 18, fill: INK2, textAnchor: 'middle' })
  g += path(`M1560 580 C 900 760, 300 760, 150 310`, { stroke: ACC, strokeDasharray: '6 6', markerEnd: 'url(#arA)', opacity: 0.8 })
  g += text(860, 735, 'learn / online 模式：程序提取已验证事实，写回经验', { fontSize: 19, fill: ACC2, textAnchor: 'middle' })
  svg('arch', g)
}

// ---------- router diagram ----------
{
  let g = ''
  g += node(20, 260, 220, 110, '可见状态', '证据 · 预算 · 合法选项', { ss: 17 })
  g += node(320, 240, 260, 150, 'ActionRouter', '下一步做什么', { hot: true, fs: 30 })
  g += arrow(240, 315, 320, 315)
  const acts = [['analyze', 40], ['propose_candidate', 110], ['profile_candidate', 400], ['run_validation', 470], ['finish', 540]]
  acts.forEach(([a, y], i) => {
    const gen = i < 2
    g += rect(660, y, 300, 56, { rx: 28, fill: gen ? 'rgba(255,90,31,0.10)' : PANEL2, stroke: gen ? 'rgba(255,90,31,0.6)' : LINE2 })
    g += text(810, y + 36, a, { textAnchor: 'middle', fontFamily: MONO, fontSize: 21, fill: gen ? ACC2 : INK })
    g += path(`M580 315 C 620 315, 620 ${y + 28}, 660 ${y + 28}`, { stroke: gen ? ACC : INK3, strokeWidth: 1.5 })
  })
  g += text(810, 24, '需要生成 → 交给 ModelRouter', { textAnchor: 'middle', fontSize: 19, fill: ACC2 })
  g += text(810, 384, '程序直接执行，不调用生成模型', { textAnchor: 'middle', fontSize: 19, fill: INK2 })
  // model router block
  g += node(660, 190, 300, 120, 'ModelRouter', 'small → large 单向升级', { hot: true, fs: 26 })
  g += arrow(810, 166, 810, 190)
  g += text(20, 470, 'llm：生成模型自选动作', { fontSize: 20, fill: INK2 })
  g += text(20, 504, 'decisions：gpt-6-luna 从合法项中选', { fontSize: 20, fill: INK2 })
  g += text(20, 556, 'rule：连续 2 个未达标', { fontSize: 18, fill: INK3 }) + text(20, 584, '或 3 次小模型请求即升级', { fontSize: 18, fill: INK3 })
  svg('router', g)
}

// ---------- sandbox ----------
{
  let g = ''
  const layers = [['宿主机 · 评测器（模型不可见、不可改）', 0, 0, 760, 420, INK3], ['每个样本一个全新容器', 40, 70, 680, 320, INK2], ['候选程序（只挂载候选文件）', 90, 150, 580, 180, ACC]]
  layers.forEach(([t, x, y, w, h, c], i) => {
    g += rect(x, y, w, h, { rx: 20, fill: i === 2 ? 'rgba(255,90,31,0.08)' : 'rgba(255,255,255,0.02)', stroke: c, strokeWidth: i === 2 ? 2.5 : 1.5, strokeDasharray: i === 1 ? '8 6' : 'none' })
    g += text(x + 24, y + 40, t, { fontSize: 22, fontWeight: 700, fill: i === 2 ? ACC2 : INK })
  })
  const tags = ['禁网', '只读根文件系统', '非 root', '1 CPU · 1 GB', '64 进程', 'stdin 输入']
  tags.forEach((t, i) => { const x = 116 + (i % 3) * 180, y = 210 + Math.floor(i / 3) * 56; g += rect(x, y, 166, 42, { rx: 21, fill: PANEL2, stroke: LINE2 }); g += text(x + 83, y + 28, t, { textAnchor: 'middle', fontSize: 19 }) })
  g += text(70, 368, '参考输出留在宿主机 · 计时从容器内启动器就绪开始', { fontSize: 18, fill: INK2 })
  // alternating timing strip
  g += text(0, 480, '交替计时 · 预热后 5 轮', { fontSize: 22, fontWeight: 700 })
  const B = [212, 205, 218, 209, 214], Cc = [151, 148, 156, 150, 153]
  for (let i = 0; i < 5; i++) {
    const x = 20 + i * 146
    g += rect(x, 505, 62, 34, { rx: 6, fill: '#3A3D46', stroke: 'none' }); g += text(x + 31, 528, 'B', { textAnchor: 'middle', fontFamily: MONO, fontSize: 18, fill: INK2 })
    g += rect(x + 68, 505, 62, 34, { rx: 6, fill: 'rgba(255,90,31,0.35)', stroke: 'none' }); g += text(x + 99, 528, 'C', { textAnchor: 'middle', fontFamily: MONO, fontSize: 18, fill: INK })
  }
  // dot strip: every candidate sample faster than every baseline sample
  const X = (ms) => 20 + (ms - 130) / (230 - 130) * 700
  g += line(20, 630, 720, 630, { stroke: LINE2 })
  B.forEach((v) => { g += `<circle cx="${X(v)}" cy="630" r="10" fill="#5A5F6B"/>` })
  Cc.forEach((v) => { g += `<circle cx="${X(v)}" cy="630" r="10" fill="${ACC}"/>` })
  g += line(X(184), 600, X(184), 660, { stroke: INK2, strokeDasharray: '4 4' })
  g += text(X(151), 594, '候选 5 个样本', { textAnchor: 'middle', fontSize: 18, fill: ACC2 })
  g += text(X(212), 594, '基线 5 个样本', { textAnchor: 'middle', fontSize: 18, fill: INK2 })
  g += text(20, 688, '全部分开（U = 0）且加速比 ≥ 1.10× 才算达标　·　示意', { fontSize: 18, fill: INK3 })
  svg('sandbox', g)
}

// ---------- verdicts & A-01 chain ----------
{
  const parts = [['支持', 371, ACC], ['部分支持', 36, ACC2], ['反驳', 100, SLATE], ['未能检验', 29, '#4A4D55']]
  const tot = parts.reduce((a, p) => a + p[1], 0)
  let g = '', x = 0
  parts.forEach(([n, v, c]) => {
    const w = v / tot * 1000
    g += rect(x, 40, w - 3, 70, { rx: 6, fill: c, stroke: 'none' })
    const k = parts.findIndex((p) => p[0] === n), lx = k * 250
    g += `<rect x="${lx}" y="146" width="16" height="16" rx="3" fill="${c}"/>` + text(lx + 26, 161, n, { fontSize: 22, fill: INK2 })
    g += text(lx, 214, String(v), { fontSize: 44, fontWeight: 800, fontFamily: NUM, fill: n === '支持' ? ACC : INK })
    x += w
  })
  g += text(0, 26, '复用实验 215 · 模型实验 321', { fontSize: 18, fill: INK3, fontFamily: SANS })
  svg('verdicts', g)
  const chain = [['c1', '0.90×', '反驳', 'Qwen', false], ['c2', '格式错误', '未能检验', 'Qwen', false], ['升级', '连续 2 个未达标', '规则触发', 'rule', 'up'], ['c3', '1.45×', '支持', 'GPT', true]]
  let h = ''
  chain.forEach(([id, v, verdict, who, hot], i) => {
    const x = i * 252
    if (hot === 'up') {
      h += rect(x, 30, 220, 170, { rx: 16, fill: 'rgba(255,90,31,0.06)', stroke: ACC, strokeDasharray: '6 6' })
      h += text(x + 110, 90, '↑ 升级大模型', { textAnchor: 'middle', fontSize: 24, fontWeight: 700, fill: ACC2 })
      h += text(x + 110, 130, v, { textAnchor: 'middle', fontSize: 19, fill: INK2 }); h += text(x + 110, 162, '读取具体反馈', { textAnchor: 'middle', fontSize: 19, fill: INK2 })
    } else {
      h += rect(x, 30, 220, 170, { rx: 16, fill: hot ? 'rgba(255,90,31,0.10)' : PANEL, stroke: hot ? ACC : LINE2 })
      h += text(x + 22, 70, id, { fontFamily: MONO, fontSize: 22, fill: INK2 }); h += text(x + 198, 70, who, { fontFamily: MONO, fontSize: 18, fill: INK3, textAnchor: 'end' })
      h += text(x + 22, 132, v, { fontFamily: NUM, fontWeight: 800, fontSize: v.length > 5 ? 32 : 46, fill: hot ? ACC : INK })
      h += text(x + 22, 178, verdict, { fontSize: 21, fill: hot ? ACC2 : INK2 })
    }
    if (i < 3) h += arrow(x + 222, 115, x + 250, 115, i === 2)
  })
  svg('chain', h)
}

// ---------- snapshot lineage ----------
{
  let g = ''
  const v = (x, y, label, sub, hot) => `<circle cx="${x}" cy="${y}" r="${hot ? 30 : 24}" fill="${hot ? ACC : PANEL2}" stroke="${hot ? ACC : LINE2}" stroke-width="2"/>`
    + text(x, y + 7, label, { textAnchor: 'middle', fontFamily: MONO, fontSize: 19, fontWeight: 700, fill: hot ? '#0C0D0F' : INK })
    + (sub ? text(x, y + 66, sub, { textAnchor: 'middle', fontSize: 18, fill: INK2 }) : '')
  g += v(50, 160, 'v0', '空库')
  g += path('M80 160 C 180 160, 180 60, 290 60', { stroke: INK3, strokeDasharray: '6 6' })
  g += v(320, 60, 'v6', ''); g += text(370, 52, 'v1 · 只存文字经验 · 13 条', { fontSize: 19, fill: INK2 }); g += text(370, 80, '留出集加速比 1.41× → 1.29× ✕', { fontSize: 19, fill: INK3 })
  g += line(80, 160, 300, 160, { stroke: ACC, strokeWidth: 3 })
  g += text(190, 148, 'A 批学习 两轮', { textAnchor: 'middle', fontSize: 17, fill: ACC2 })
  g += v(330, 160, 'v19', '59 条 · 可执行程序', true)
  g += line(362, 160, 640, 160, { stroke: ACC, strokeWidth: 3 })
  g += text(500, 148, 'S 在线任务流', { textAnchor: 'middle', fontSize: 17, fill: ACC2 })
  g += v(670, 160, 'v…', '每次重放 59 → 77 条', true)
  g += path('M330 196 C 330 270, 220 280, 140 280', { stroke: SLATE, strokeDasharray: '5 5', markerEnd: 'url(#ar)' })
  g += text(350, 286, 'activate v0：只移动默认指针，快照本身不变', { fontSize: 18, fill: SLATE })
  svg('lineage', g)
}

// ---------- triage tree ----------
{
  let g = ''
  g += node(330, 0, 340, 90, '新任务到达', '先复验 ≤ 3 个已验证程序', { ss: 17 })
  g += node(330, 150, 340, 90, '复验达标？', '', {})
  g += arrow(500, 90, 500, 150)
  g += node(760, 150, 230, 90, '直接交付', '0 次模型调用', { hot: true, ss: 18 })
  g += arrow(670, 195, 760, 195); g += text(715, 183, '是', { textAnchor: 'middle', fontSize: 19, fill: ACC2 })
  g += node(330, 310, 340, 100, '经验覆盖如何？', '同族记录 · 条件匹配 ≥ 3/5', { ss: 17 })
  g += arrow(500, 240, 500, 310); g += text(516, 282, '否', { fontSize: 19, fill: INK2 })
  const leaves = [[0, '相近成功', '先用本地小模型', '便宜，常常够用', false], [340, '全新任务族', '直接交给大模型', '整份预算给大模型', true], [680, '新条件', '直接交给大模型', '有记录但无相近成功', true]]
  leaves.forEach(([x, k, a, b, hot]) => {
    g += path(`M500 410 C 500 450, ${x + 150} 440, ${x + 150} 480`, { stroke: hot ? ACC : INK2, markerEnd: `url(#${hot ? 'arA' : 'ar'})` })
    g += text(x + 150, 470 - 4, '', {})
    g += rect(x, 480, 300, 140, { rx: 16, fill: hot ? 'rgba(255,90,31,0.08)' : PANEL, stroke: hot ? ACC : LINE2 })
    g += text(x + 24, 522, k, { fontFamily: SANS, fontSize: 20, fill: INK2 })
    g += text(x + 24, 566, a, { fontSize: 28, fontWeight: 700, fill: hot ? ACC2 : INK })
    g += text(x + 24, 602, b, { fontSize: 19, fill: INK3 })
  })
  svg('triage', g)
}

// ---------- 7 candidates step chart ----------
{
  const W = 1728, x0 = 150, x1 = 1600, y0 = 40, y1 = 560, lo = 43800, hi = 47100
  const X = (s) => x0 + s / 360 * (x1 - x0), Y = (v) => y1 - (v - lo) / (hi - lo) * (y1 - y0)
  const C = [[12.851, 44120, 's', '44,120', 'b'], [22.792, 44120, 's', '同一份代码', 'a'], [94.286, 46506, 'l', '分段规划 · 46,506', 'a'], [178.438, 46798, 'l', '局部搜索 · 46,798', 'a'],
    [244.796, 46725, 'x', '46,725 · 下降，被拦下', 'b'], [311.463, 46800, 'l', '46,800', 'b'], [357.026, 46849, 'l', '复用后缀 · 46,849', 'e']]
  let g = ''
  for (const v of [44000, 45000, 46000, 47000]) { g += line(x0, Y(v), x1, Y(v), { stroke: LINE, strokeWidth: 1.5 }); g += text(x0 - 20, Y(v) + 8, fmt(v), { textAnchor: 'end', fontSize: 22, fill: INK3, fontFamily: NUM, fontWeight: 600 }) }
  for (const s of [0, 60, 120, 180, 240, 300]) g += text(X(s), y1 + 44, `${s}s`, { textAnchor: 'middle', fontSize: 21, fill: INK3, fontFamily: MONO })
  g += line(x0, y1, x1, y1, { stroke: LINE2 })
  g += line(X(360), y0 - 20, X(360), y1, { stroke: INK2, strokeDasharray: '8 8' }); g += text(X(360), y1 + 44, '360s 预算', { textAnchor: 'middle', fontSize: 21, fill: INK, fontFamily: MONO })
  // small vs large zones
  g += rect(x0, y0 - 20, X(26) - x0, y1 - y0 + 20, { rx: 0, fill: 'rgba(127,141,166,0.07)', stroke: 'none' })
  g += rect(X(26), y0 - 20, X(360) - X(26), y1 - y0 + 20, { rx: 0, fill: 'rgba(255,90,31,0.04)', stroke: 'none' })
  g += text(x0 + 12, y1 - 16, 'Qwen', { fontSize: 19, fill: SLATE, fontFamily: MONO })
  g += text(X(26) + 14, y1 - 16, 'gpt-6.1-sol', { fontSize: 19, fill: ACC2, fontFamily: MONO })
  g += line(X(26), y0 - 20, X(26), y1, { stroke: ACC, strokeWidth: 3, strokeDasharray: '10 8' })
  g += text(X(26) + 18, Y(45350), '连续两次没进步', { fontSize: 26, fontWeight: 700 }); g += text(X(26) + 18, Y(45350) + 38, '→ 按规则升级大模型', { fontSize: 26, fontWeight: 700, fill: ACC })
  // best-so-far step line
  let d = '', best = null
  for (const [s, v, m] of C) { if (m === 'x') continue; if (best == null) d = `M${X(s)} ${Y(v)}`; else d += ` H${X(s)} V${Y(Math.max(best, v))}`; best = Math.max(best ?? -1, v) }
  d += ` H${X(360)}`
  g += path(d + ` V${y1} H${X(12.851)} Z`, { fill: 'url(#fadeA)', stroke: 'none', opacity: 0.45 })
  g += path(d, { stroke: ACC, strokeWidth: 12, filter: 'url(#glow2)', opacity: 0.6 })
  g += path(d, { stroke: ACC, strokeWidth: 5, strokeLinejoin: 'round' })
  g += text(X(102), Y(45200), '+2,386', { fontSize: 110, fontWeight: 800, fontFamily: NUM, fill: ACC, letterSpacing: -3 })
  C.forEach(([s, v, m, lab, pos], i) => {
    const cx = X(s), cy = Y(v)
    if (m === 'x') g += `<circle cx="${cx}" cy="${cy}" r="18" fill="#0C0D0F" stroke="${INK2}" stroke-width="3"/>` + path(`M${cx - 9} ${cy - 9} L${cx + 9} ${cy + 9} M${cx + 9} ${cy - 9} L${cx - 9} ${cy + 9}`, { stroke: INK, strokeWidth: 4, strokeLinecap: 'round' })
    else g += `<circle cx="${cx}" cy="${cy}" r="14" fill="${m === 's' ? SLATE : ACC}" stroke="#0C0D0F" stroke-width="5"/>`
    const ly = pos === 'b' ? cy + 54 : cy - 50, anc = pos === 'e' ? 'end' : pos === 'a' && i === 1 ? 'end' : 'middle', lx = pos === 'e' ? cx + 10 : i === 1 ? cx + 10 : cx
    g += text(lx, ly, lab, { textAnchor: anc, fontSize: 24, fontWeight: 700, fill: m === 'x' ? INK2 : INK })
  })
  svg('steps', g)
}

// ---------- routing ablation ----------
{
  const R = [['LLM / rule', '基线', 5.970, 392.0], ['Decisions / rule', '仅动作', 6.149, 389.4], ['LLM / Decisions', '仅模型', 5.836, 389.9], ['Decisions / Decisions', '双决策', 0.513, 112.9]]
  let g = ''
  g += text(300, 30, '相对 c0 的 final 提升', { fontSize: 20, fill: INK3, fontFamily: MONO })
  g += text(790, 30, '整轮用时（含 final）', { fontSize: 20, fill: INK3, fontFamily: MONO })
  R.forEach(([n, k, gain, sec], i) => {
    const y = 70 + i * 120, hot = i === 1
    g += text(0, y + 34, n, { fontFamily: MONO, fontSize: 22, fontWeight: 700, fill: hot ? ACC2 : INK })
    g += text(0, y + 66, k, { fontSize: 20, fill: INK3 })
    const w1 = gain / 7 * 360
    g += rect(300, y + 10, w1, 56, { rx: 6, fill: hot ? 'url(#barA)' : 'url(#barS)', stroke: 'none' })
    g += text(300 + w1 + 14, y + 50, `+${gain.toFixed(2)}%`, { fontFamily: NUM, fontWeight: 800, fontSize: 32, fill: hot ? ACC : INK })
    const w2 = sec / 420 * 300
    g += rect(790, y + 10, w2, 56, { rx: 6, fill: i === 3 ? 'url(#barA)' : '#3A3D46', stroke: 'none' })
    g += text(790 + w2 + 14, y + 50, `${sec.toFixed(0)} s`, { fontFamily: NUM, fontWeight: 800, fontSize: 32, fill: i === 3 ? ACC : INK })
  })
  g += line(300, 50, 300, 540, { stroke: LINE2 }); g += line(790, 50, 790, 540, { stroke: LINE2 })
  g += text(0, 552, '预算统一：360 s · 20 次请求（含路由）· 10 个候选 · 每组 1 次', { fontSize: 19, fill: INK3 })
  svg('routes', g)
}

// ---------- two hosts ----------
{
  const S = [['固定小模型', 0.00, 0.00], ['固定大模型', 5.73, 5.50], ['规则自适应', 6.37, 5.43], ['Decisions 动作路由', 5.82, 6.34]]
  const y1 = 470, sc = 60
  let g = ''
  for (const v of [0, 2, 4, 6]) { g += line(60, y1 - v * sc, 1090, y1 - v * sc, { stroke: LINE, strokeWidth: 1.5 }); g += text(46, y1 - v * sc + 8, `${v}%`, { textAnchor: 'end', fontSize: 20, fill: INK3, fontFamily: MONO }) }
  S.forEach(([n, d, l], i) => {
    const cx = 120 + i * 250
    ;[[d, 'desktop', '#3E4A60', SLATE], [l, 'laptop', '#7A2E12', ACC]].forEach(([v, host, c0, c1], j) => {
      const x = cx + j * 92, h = Math.max(4, v * sc)
      g += rect(x, y1 - h, 78, h, { rx: 6, fill: c1, stroke: 'none', opacity: j ? 0.95 : 0.9 })
      g += text(x + 39, y1 - h - 14, `${v.toFixed(2)}`, { textAnchor: 'middle', fontFamily: NUM, fontWeight: 800, fontSize: 24, fill: INK })
    })
    g += text(cx + 85, y1 + 44, n, { textAnchor: 'middle', fontSize: 22, fontWeight: 700 })
  })
  g += `<circle cx="70" cy="560" r="9" fill="${SLATE}"/>` + text(88, 567, 'desktop', { fontSize: 20, fill: INK2, fontFamily: MONO })
  g += `<circle cx="230" cy="560" r="9" fill="${ACC}"/>` + text(248, 567, 'laptop', { fontSize: 20, fill: INK2, fontFamily: MONO })
  g += text(1090, 567, '相对 c0 的 final 提升（%）· c0 = 131,864', { fontSize: 19, fill: INK3, textAnchor: 'end' })
  svg('hosts', g)
}

// ---------- memory: paired before/after rows ----------
function pairs(id, rows) {
  let g = ''
  rows.forEach(([name, a, b, la, lb, better], i) => {
    const y = 40 + i * 120, max = Math.max(a, b) || 1
    g += text(0, y + 4, name, { fontSize: 23, fontWeight: 700 })
    const wa = Math.max(4, a / max * 470), wb = Math.max(4, b / max * 470)
    g += rect(0, y + 22, wa, 26, { rx: 5, fill: '#3A3D46', stroke: 'none' }); g += text(wa + 12, y + 44, la, { fontFamily: NUM, fontWeight: 700, fontSize: 24, fill: INK2 })
    g += rect(0, y + 56, wb, 26, { rx: 5, fill: 'url(#barA)', stroke: 'none' }); g += text(wb + 12, y + 78, lb, { fontFamily: NUM, fontWeight: 800, fontSize: 26, fill: ACC })
    g += text(760, y + 4, better, { textAnchor: 'end', fontSize: 19, fill: INK3, fontFamily: MONO })
  })
  svg(id, g)
}
pairs('memD', [['达标 / 运行', 15, 18, '15/18', '18/18', '越高越好'], ['最终加速比中位数', 1.20, 1.73, '1.20×', '1.73×', '越高越好'], ['模型请求合计', 52, 0, '52', '0', '越低越好'], ['总耗时', 1782, 669, '1782 s', '669 s', '越低越好']])
pairs('memS', [['大模型（GPT）请求', 27, 6, '27', '6', '越低越好'], ['零模型调用的运行', 9, 30, '9/36', '30/36', '越高越好'], ['模型费用（估算）', 0.402, 0.086, '$0.402', '$0.086', '越低越好'], ['总耗时', 1486, 1064, '1486 s', '1064 s', '越低越好']])

// ---------- AlgoTune bars ----------
{
  const A = [['PageRank', 'feedback', 25.04], ['PageRank', 'independent', 23.05], ['一维卷积', 'independent', 2.67], ['一维卷积', 'feedback', 1.30]]
  let g = ''
  A.forEach(([t, s, v], i) => {
    const y = 20 + i * 128, w = v / 31 * 760
    g += text(0, y + 40, t, { fontSize: 26, fontWeight: 700 }); g += text(0, y + 74, s, { fontSize: 20, fill: INK3, fontFamily: MONO })
    g += rect(230, y + 10, Math.max(w, 6), 70, { rx: 8, fill: i === 0 ? 'url(#barA)' : 'url(#barS)', stroke: 'none' })
    g += text(230 + Math.max(w, 6) + 16, y + 60, `${v.toFixed(2)}×`, { fontFamily: NUM, fontWeight: 800, fontSize: 40, fill: i === 0 ? ACC : INK })
  })
  g += line(230, 10, 230, 520, { stroke: LINE2 })
  g += text(0, 548, '2 个开发输入 × 5 次计时重复 · 关闭最终测试 · Mac 开发测试', { fontSize: 19, fill: INK3 })
  svg('algo', g)
}

// ---------- console screenshots, fanned out ----------
{
  const c = $('console')
  const shots = [['/frontend/docs/screenshots/run-1440-dark.png', '运行：假设、判定与用量', 0, 60, 540, 520, 8], ['/frontend/docs/screenshots/live-1440-preview-dark.png', '实时：研究进度与预算', 1188, 60, 540, 520, -8], ['/frontend/docs/screenshots/res-1440-dark.png', '研究对照：各策略逐轮结果', 404, 0, 920, 640, 0]]
  c.innerHTML = shots.map(([src, cap, x, y, w, h, r]) => `<div style="position:absolute; left:${x}px; top:${y}px; width:${w}px; transform: perspective(1800px) rotateY(${r}deg); ${r ? 'opacity:.85' : 'z-index:2'}">
    <div class="shot" style="height:${h}px; background:#0C0D0F"><img src="${src}" style="width:100%"></div><div class="cap" style="margin-top:16px; text-align:center; font-size:24px; color:var(--ink)">${cap}</div></div>`).join('')
}

window.deckReady = true
