// QuotaCrux 枢决 showcase video. Everything on screen is a pure function of time t (seconds): window.render(t).
import * as THREE from 'three'

const C = { bg: 0xF1EFE9, ink: '#111113', grey: '#8E8D88', accent: '#FF4D1F', card: '#D6B98D', cardEdge: '#B4925F' }
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v))
const seg = (t, a, b) => clamp((t - a) / (b - a))
const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2)
const easeOut = (x) => 1 - Math.pow(1 - x, 3)
const lerp = (a, b, f) => a + (b - a) * f
function bounce(x) {
  const n = 7.5625, d = 2.75
  if (x < 1 / d) return n * x * x
  if (x < 2 / d) return n * (x -= 1.5 / d) * x + 0.75
  if (x < 2.5 / d) return n * (x -= 2.25 / d) * x + 0.9375
  return n * (x -= 2.625 / d) * x + 0.984375
}

// ---------- data ----------
const replay = await (await fetch('./data/replay.json')).json()
const N = 200, M = 10, BOX_H = 0.4, GAP_X = 1.4
const stackX = (i) => (i - (M - 1) / 2) * GAP_X

// ---------- scene ----------
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('gl'), antialias: true, preserveDrawingBuffer: true })
renderer.setPixelRatio(1)
renderer.setSize(1920, 1080, false)
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.PCFSoftShadowMap
renderer.outputColorSpace = THREE.SRGBColorSpace
renderer.toneMapping = THREE.ACESFilmicToneMapping
renderer.toneMappingExposure = 1.05
const scene = new THREE.Scene()
scene.background = new THREE.Color(C.bg)
scene.fog = new THREE.Fog(C.bg, 45, 95)
const camera = new THREE.PerspectiveCamera(32, 1920 / 1080, 0.1, 300)

scene.add(new THREE.HemisphereLight(0xfff8ee, 0xcfc6b6, 1.5))
const sun = new THREE.DirectionalLight(0xfff1dc, 2.6)
sun.position.set(-10, 22, 16)
sun.castShadow = true
sun.shadow.mapSize.set(4096, 4096)
sun.shadow.bias = -0.0004
Object.assign(sun.shadow.camera, { left: -18, right: 18, top: 30, bottom: -6, near: 1, far: 80 })
scene.add(sun)
const fill = new THREE.DirectionalLight(0xdfe8ff, 0.6)
fill.position.set(12, 8, 10)
scene.add(fill)

const floor = new THREE.Mesh(new THREE.PlaneGeometry(300, 300), new THREE.MeshStandardMaterial({ color: 0xE4E0D6, roughness: 1 }))
floor.rotation.x = -Math.PI / 2
floor.receiveShadow = true
scene.add(floor)
const grid = new THREE.GridHelper(80, 80, 0xC9C3B6, 0xD6D1C5)
grid.position.y = 0.003
grid.material.transparent = true
grid.material.opacity = 0.55
scene.add(grid)
for (let i = 0; i < M; i++) {
  const slot = new THREE.Mesh(new THREE.PlaneGeometry(1.22, 1.12), new THREE.MeshBasicMaterial({ color: 0xD3CDBF }))
  slot.rotation.x = -Math.PI / 2
  slot.position.set(stackX(i), 0.006, 0)
  scene.add(slot)
}

// research loop drawn on the floor around the warehouse
const loopPts = []
{
  const hw = 8.3, hd = 2.4, r = 1.6, n = 40
  const corner = (cx, cz, a0) => { for (let i = 0; i <= n; i++) { const a = a0 + (i / n) * Math.PI / 2; loopPts.push(new THREE.Vector3(cx + r * Math.cos(a), 0.06, cz + r * Math.sin(a))) } }
  corner(hw - r, hd - r, 0); corner(-hw + r, hd - r, Math.PI / 2); corner(-hw + r, -hd + r, Math.PI); corner(hw - r, -hd + r, Math.PI * 1.5)
}
const loopCurve = new THREE.CatmullRomCurve3(loopPts, true)
const TUBE_SEG = 600
const tube = new THREE.Mesh(new THREE.TubeGeometry(loopCurve, TUBE_SEG, 0.07, 10, true), new THREE.MeshBasicMaterial({ color: C.accent }))
const glow = new THREE.Mesh(new THREE.TubeGeometry(loopCurve, TUBE_SEG, 0.24, 10, true),
  new THREE.MeshBasicMaterial({ color: C.accent, transparent: true, opacity: 0.16, depthWrite: false }))
scene.add(tube, glow)
const drawTube = (f) => { for (const m of [tube, glow]) m.geometry.setDrawRange(0, Math.floor(TUBE_SEG * f) * 10 * 6) }

// boxes
function labelTexture(n, hot, square) {
  const c = document.createElement('canvas')
  c.width = 256; c.height = square ? 236 : 104
  const g = c.getContext('2d')
  g.fillStyle = hot ? C.accent : C.card
  g.fillRect(0, 0, c.width, c.height)
  g.strokeStyle = hot ? '#C93A12' : C.cardEdge
  g.lineWidth = 7
  g.strokeRect(3.5, 3.5, c.width - 7, c.height - 7)
  if (square) { g.fillStyle = hot ? 'rgba(255,255,255,0.25)' : 'rgba(150,115,70,0.28)'; g.fillRect(110, 0, 36, c.height) }
  g.fillStyle = hot ? '#ffffff' : C.ink
  g.font = `800 ${square ? 92 : 70}px "Avenir Next", sans-serif`
  g.textAlign = 'center'; g.textBaseline = 'middle'
  g.fillText(String(n), 128, c.height / 2 + 5)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 8
  return tex
}
const boxGeo = new THREE.BoxGeometry(1.0, BOX_H * 0.94, 0.92)
const sideMat = new THREE.MeshStandardMaterial({ color: 0xC4A271, roughness: 0.92 })
const boxes = new Map()
for (let v = 1; v <= N; v++) {
  const front = new THREE.MeshStandardMaterial({ map: labelTexture(v, false, false), roughness: 0.88 })
  const top = new THREE.MeshStandardMaterial({ map: labelTexture(v, false, true), roughness: 0.88 })
  const mesh = new THREE.Mesh(boxGeo, [sideMat, sideMat, top, sideMat, front, sideMat])
  mesh.castShadow = true; mesh.receiveShadow = true
  mesh.userData = { front, top, plain: [front.map, top.map], hot: null }
  scene.add(mesh)
  boxes.set(v, mesh)
}
function setHot(v, on) {
  const u = boxes.get(v).userData
  if (on && !u.hot) u.hot = [labelTexture(v, true, false), labelTexture(v, true, true)]
  const maps = on ? u.hot : u.plain
  if (u.front.map !== maps[0]) { u.front.map = maps[0]; u.top.map = maps[1]; u.front.needsUpdate = u.top.needsUpdate = true }
}

// pulsing ring on the floor under the stack that holds the next box to carry out
const ring = new THREE.Mesh(new THREE.RingGeometry(0.85, 1.0, 64), new THREE.MeshBasicMaterial({ color: C.accent, transparent: true, depthWrite: false }))
ring.rotation.x = -Math.PI / 2
ring.position.y = 0.02
scene.add(ring)

// arc trail for a move
const trailGeo = new THREE.BufferGeometry()
const trail = new THREE.Line(trailGeo, new THREE.LineDashedMaterial({ color: C.accent, dashSize: 0.25, gapSize: 0.18, transparent: true }))
scene.add(trail)

// research-loop props: station discs, a moving chip and the glass judge in the middle
const STATIONS = [['规划', -5, -2.4], ['取证', 0, -2.4], ['假设', 5, -2.4], ['实验', 5, 2.4], ['验证', 0, 2.4], ['修正', -5, 2.4]]
const loopLen = loopCurve.getLength()
const nearestU = (x, z) => {
  let best = 0, bd = Infinity
  for (let i = 0; i < 2000; i++) { const q = loopCurve.getPointAt(i / 2000), d = (q.x - x) ** 2 + (q.z - z) ** 2; if (d < bd) { bd = d; best = i / 2000 } }
  return best
}
const stationU = STATIONS.map(([, x, z]) => nearestU(x, z))
const discs = STATIONS.map(([, x, z]) => {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.08, 40), new THREE.MeshStandardMaterial({ color: 0x111113, roughness: 0.6 }))
  m.position.set(x, 0.07, z); m.receiveShadow = true; scene.add(m); return m
})
const chip = new THREE.Mesh(new THREE.SphereGeometry(0.34, 32, 20), new THREE.MeshStandardMaterial({ color: 0x111113, roughness: 0.35 }))
chip.castShadow = true
const chipGlow = new THREE.Mesh(new THREE.SphereGeometry(0.7, 24, 16), new THREE.MeshBasicMaterial({ color: C.accent, transparent: true, opacity: 0.18, depthWrite: false }))
scene.add(chip, chipGlow)
const judge = new THREE.Group()
{
  const g = new THREE.BoxGeometry(4.4, 1.9, 2.0)
  const glass = new THREE.Mesh(g, new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.32, roughness: 0.08, metalness: 0, depthWrite: false }))
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(g), new THREE.LineBasicMaterial({ color: 0x111113, transparent: true }))
  judge.add(glass, edges)
  judge.userData = { edges }
  judge.position.set(0, 0.95, 0)
  scene.add(judge)
}

// ---------- timeline helpers ----------
// a replay schedule is a list of [t, p] keyframes, piecewise linear and non-decreasing in p
function pAt(K, t) {
  if (t <= K[0][0]) return K[0][1]
  for (let i = 1; i < K.length; i++) if (t <= K[i][0]) { const [t0, p0] = K[i - 1], [t1, p1] = K[i]; return p0 + (p1 - p0) * (t - t0) / (t1 - t0) }
  return K[K.length - 1][1]
}
function tAt(K, p) {
  for (let i = 1; i < K.length; i++) { const [t0, p0] = K[i - 1], [t1, p1] = K[i]; if (p <= p1 && p1 > p0) return t0 + (t1 - t0) * Math.max(0, p - p0) / (p1 - p0) }
  return K[K.length - 1][0]
}
const fade = (t, a, b, fi = 0.5, fo = 0.4) => Math.min(easeOut(seg(t, a, a + fi)), 1 - seg(t, b - fo, b))
const fmt = (n) => Math.round(n).toLocaleString('en-US')

// ---------- replay ----------
function buildReplay(steps) {
  const states = [replay.stacks.map((s) => s.slice())]
  for (const s of steps) {
    const st = states[states.length - 1].map((a) => a.slice())
    if (s.op === 'out') st[s.from].pop()
    else { const j = st[s.from].indexOf(s.v); const moved = st[s.from].splice(j); st[s.to].push(...moved) }
    states.push(st)
  }
  return { steps, states, H: states.map((st) => Math.max(...st.map((a) => a.length))) }
}
const R0 = buildReplay(replay.c0.steps), R7 = buildReplay(replay.c7.steps)
const basePos = (st) => {
  const pos = new Map()
  st.forEach((stack, i) => stack.forEach((v, j) => pos.set(v, [stackX(i), BOX_H / 2 + j * BOX_H, 0])))
  return pos
}
const dropStart = (si, j) => 0.15 + si * 0.07 + j * 0.05

/** Place boxes for replay progress p. `drop` is the time since a fall-in began (or null); `fast` hides per-move dressing. */
function placeReplay(R, p, drop, fast) {
  const n = R.steps.length
  const k = clamp(Math.floor(p), 0, n), f = k < n ? p - k : 0
  const st = R.states[k]
  const pos = basePos(st)
  for (const [v, mesh] of boxes) {
    const q = pos.get(v)
    mesh.visible = !!q
    if (!q) continue
    mesh.position.set(q[0], q[1], q[2]); mesh.scale.setScalar(1); mesh.rotation.set(0, 0, 0)
    if (drop != null) {
      const si = st.findIndex((a) => a.includes(v)), j = st[si].indexOf(v)
      const start = dropStart(si, j), g = seg(drop, start, start + 0.7)
      mesh.visible = drop >= start
      mesh.position.y = q[1] + (1 - bounce(g)) * 10
      mesh.rotation.y = (1 - easeOut(g)) * 0.5 * (si % 2 ? 1 : -1)
    }
  }
  let energy = k > 0 ? R.steps[k - 1].energy : 0, move = null
  trail.visible = false
  if (k < n && f > 0) {
    const s = R.steps[k], e = ease(f)
    if (s.op === 'out') {
      const mesh = boxes.get(s.v), q = pos.get(s.v)
      mesh.position.set(q[0], q[1] + Math.sin(e * Math.PI) * 1.2, q[2] + e * 7)
      mesh.scale.setScalar(1 - 0.7 * e)
    } else {
      const src = st[s.from], j = src.indexOf(s.v), moved = src.slice(j)
      const dstH = st[s.to].length
      const lift = Math.max(src.length - moved.length, dstH) * BOX_H + moved.length * BOX_H + 0.8
      const x0 = stackX(s.from), x1 = stackX(s.to), baseY = pos.get(moved[0])[1]
      moved.forEach((v, idx) => {
        const y0 = pos.get(v)[1], y1 = BOX_H / 2 + (dstH + idx) * BOX_H, top = lift - (moved.length - idx) * BOX_H + BOX_H
        let x, y
        if (f < 0.3) { const g = ease(f / 0.3); x = x0; y = lerp(y0, top, g) }
        else if (f < 0.7) { const g = ease((f - 0.3) / 0.4); x = lerp(x0, x1, g); y = top + Math.sin(g * Math.PI) * 0.6 }
        else { const g = ease((f - 0.7) / 0.3); x = x1; y = lerp(top, y1, g) }
        boxes.get(v).position.set(x, y, 0)
      })
      if (!fast) {
        // dashed arc from the lifted block to its landing spot
        const a = new THREE.Vector3(x0, baseY, 0.6), b = new THREE.Vector3(x1, BOX_H / 2 + dstH * BOX_H, 0.6)
        const mid = new THREE.Vector3((x0 + x1) / 2, lift + 1.2, 0.6)
        trailGeo.setFromPoints(new THREE.QuadraticBezierCurve3(a, mid, b).getPoints(48))
        trail.computeLineDistances()
        trail.material.opacity = Math.sin(clamp(f) * Math.PI)
        trail.visible = true
      }
      if (f > 0.5) energy = s.energy
      move = { s, f, land: new THREE.Vector3(x1, BOX_H / 2 + (dstH + moved.length) * BOX_H + 0.4, 0) }
    }
  }
  return { energy, move, k, st }
}

// ---------- timeline ----------
// c0 on its own: slow rules demo (the first move buries box 8; step 14 pays for it), then fast-forward to the end
const K0 = [[10.8, 0], [12.2, 1], [13.0, 2], [19.0, 14], [20.8, 15], [21.5, 16], [22.0, 16], [24.0, 30], [33.0, R0.steps.length]]
// both programs side by side on the same case, by fraction of their own operation count
const KS = [[95.0, 0], [98.2, 0.035], [106.0, 1]]
const T = { costCard: [33.0, 36.8], loop: [36.8, 54.6], chart: [54.6, 92.2], split: [92.2, 114.2], result: [106.3, 114.2],
  routing: [114.2, 132.2], func: [132.2, 142.2], ledger: [142.2, 154.2], end: [154.2, 163.5] }
const END_DROP = 154.5
window.DURATION = 163.5

const SUBS = [
  [0.9, 6.0, '让 AI 做研究，贵的往往不是算力，而是一次又一次的“再试一次”。'],
  [6.6, 10.6, '200 个箱子分在 10 堆里，必须按 1、2、3 的顺序，一个个搬出仓库。'],
  [10.8, 14.9, '要拿到下面的箱子，得先把上面一整摞搬走：搬 k 个箱子，耗 k+1 份力气。'],
  [15.0, 18.7, '箱子露到最上面，就能搬出仓库，这一步不耗力气。'],
  [18.8, 22.6, '可第一步放下的那一摞，正好压住了箱子 8：现在得再花 29 份力气把它挪开。'],
  [22.8, 27.6, '每个用例的得分是 10000 减去总能耗：放法越聪明，力气越省。'],
  [27.8, 36.4, '题目给的初始程序能把箱子搬完，但 15 个用例一共耗了一万八千多份力气。'],
  [37.4, 43.4, 'QuotaCrux 把研究拆成一圈：定计划、看数据、提假设，再写成程序。'],
  [43.6, 49.2, '每版程序都交给外部裁判：在隔离环境里验对错、计时打分，好的才留下。'],
  [49.4, 54.4, '本地小模型干主力，只在关键节点请云端大模型，整轮都在预算之内。'],
  [55.2, 61.6, '这是一轮真实的研究。小模型连续两次交了同一份代码，分数原地不动。'],
  [61.8, 66.6, '连续两次没有进步，系统按规则换上云端大模型。'],
  [66.8, 71.6, '大模型学会提前看后面要拿哪个箱子，分段规划放法，分数一下涨了 2,386。'],
  [71.8, 76.6, '接着加入局部搜索，再往上一步。'],
  [76.8, 81.6, '有一版改坏了，分数下降，裁判当场拦下，系统回到上一个最好的版本。'],
  [81.8, 86.4, '从最好的版本重新出发，又小涨了 2 分。'],
  [86.6, 92.0, '最后复用相同的搬运后缀，拿到这一轮的最高分：46,849。'],
  [92.6, 99.0, '冻结最好的版本。左边是初始程序，右边是最终版本，在同一个用例上同时回放。'],
  [99.2, 106.1, '右边每次搬得更少、放得更准：这个用例的能耗从 1,158 降到 649。'],
  [106.4, 114.0, '再到从没见过的 15 个用例上只测一次：全部通过，总能耗从 18,136 降到 10,028。'],
  [114.6, 120.6, '谁来决定下一步，同样影响结果：让决策模型挑动作，这一轮得分最高。'],
  [120.8, 126.6, '全部交给决策模型，它一直没请大模型：用时少了七成，提升却只剩 0.5%。'],
  [126.8, 132.0, '在预算里做研究，就是在质量和成本之间取舍。每组只跑一次，这是探索性的观察。'],
  [132.6, 137.2, '同一套闭环也能优化单个函数：PageRank 改用稀疏矩阵直接迭代，快了 25 倍。'],
  [137.4, 142.0, '一维卷积改用 float32 实数 FFT，快了 2.67 倍。'],
  [142.6, 148.0, '每一次调用都记账：15 次交付全部通过最终测试，96 个候选里 60 个通过验证。'],
  [148.2, 154.0, '而大部分时间，都花在等模型回复上，这正是最值得省下来的地方。'],
]
const TAGS = [
  [6.0, 36.6, '01', '测试难题', 'AtCoder 启发式竞赛 · 搬箱子'],
  [37.2, 54.4, '02', '研究闭环', '规划、实验、验证，一圈一圈地改'],
  [55.0, 92.0, '03', '一轮研究', '360 秒里的 7 个候选'],
  [92.6, 114.0, '04', '隐藏测试', '冻结最好的版本'],
  [114.4, 132.0, '05', '调度对照', '谁来决定下一步'],
  [132.4, 142.0, '06', '函数级优化', '同一套闭环，换一个对象'],
  [142.4, 154.0, '07', '账本', '每一次调用都记账'],
]
const CANDS = [
  { x: 12.851, y: 44120, m: 's', t: 57.5, label: '44,120', pos: 'below' },
  { x: 22.792, y: 44120, m: 's', t: 60.0, label: '同一份代码', pos: 'aboveEnd' },
  { x: 94.286, y: 46506, m: 'l', t: 67.0, label: '+2,386 · 分段规划', pos: 'above' },
  { x: 178.438, y: 46798, m: 'l', t: 72.0, label: '局部搜索 · 46,798', pos: 'above' },
  { x: 244.796, y: 46725, m: 'x', t: 77.0, label: '46,725 · 下降，拦下', pos: 'below' },
  { x: 311.463, y: 46800, m: 'l', t: 82.0, label: '46,800', pos: 'below' },
  { x: 357.026, y: 46849, m: 'l', t: 86.5, label: '复用后缀 · 46,849', pos: 'aboveEnd' },
]
const UPGRADE = { x: 26, t: 62.4 }
// chart playhead: elapsed research seconds as a function of video time
const KP = [[56.0, 0], ...CANDS.slice(0, 2).map((c) => [c.t, c.x]), [64.6, 30], ...CANDS.slice(2).map((c) => [c.t, c.x]), [88.0, 360]]
const ROUTES = [
  ['规则选模型', '基线', 5.970, 392.0],
  ['决策模型选动作', '本轮最高分', 6.149, 389.4],
  ['决策模型选模型', '', 5.836, 389.9],
  ['两者都交给决策模型', '全程只用小模型', 0.513, 112.9],
]
const CHIP = { t0: 40.0, period: 4.6, upgradeAt: 49.6 }

// ---------- overlays ----------
const $ = (id) => document.getElementById(id)
const brand = $('brand'), tagEl = $('tag'), hud = $('hud'), sub = $('sub'), subText = sub.querySelector('span'), delta = $('delta'), pin = $('pin')
brand.innerHTML = `<div class="name">${[...'QuotaCrux'].map((ch) => `<span>${ch}</span>`).join('')}</div><div class="cn">枢决</div><div class="dot"></div>`
const letters = [...brand.querySelectorAll('.name span')], cn = brand.querySelector('.cn'), dot = brand.querySelector('.dot')
const stationEls = STATIONS.map(([name], i) => {
  const el = document.createElement('div'); el.className = 'station card'
  el.innerHTML = `<small>0${i + 1}</small>${name}`; $('stations').appendChild(el); return el
})
const judgeEl = $('judge'), chipLabel = $('chipLabel'), budget = $('budget'), sideL = $('sideL'), sideR = $('sideR'), divider = $('divider'), panel = $('panel')
budget.innerHTML = '<div class="k">一轮研究的预算</div><div class="row"><div><span class="num">360</span>秒</div><div><span class="num">20</span>次请求</div><div><span class="num">10</span>个候选</div></div>'

const P = { cost: $('p-cost'), chart: $('p-chart'), result: $('p-result'), routing: $('p-routing'), func: $('p-func'), ledger: $('p-ledger'), end: $('p-end') }
P.cost.innerHTML = '<div class="k">初始程序 · 15 个用例</div><div class="hero num" id="cost-n">0</div><div class="k2">总能耗</div>'

// step chart of the seven candidates
const SV = { w: 1688, h: 430, x0: 120, x1: 1490, y0: 34, y1: 366, lo: 43800, hi: 47100 }
const X = (s) => SV.x0 + (s / 360) * (SV.x1 - SV.x0)
const Y = (v) => SV.y1 - ((v - SV.lo) / (SV.hi - SV.lo)) * (SV.y1 - SV.y0)
{
  const ns = 'http://www.w3.org/2000/svg'
  let g = ''
  for (const v of [44000, 45000, 46000, 47000]) g += `<line x1="${SV.x0}" x2="${SV.x1}" y1="${Y(v)}" y2="${Y(v)}" stroke="#E2DED5" stroke-width="2"/><text x="${SV.x0 - 18}" y="${Y(v) + 9}" text-anchor="end" font-size="26" fill="#8E8D88" font-weight="600">${fmt(v)}</text>`
  for (const s of [0, 60, 120, 180, 240, 300]) g += `<text x="${X(s)}" y="${SV.y1 + 46}" text-anchor="middle" font-size="26" fill="#8E8D88" font-weight="600">${s}</text>`
  g += `<line x1="${SV.x0}" x2="${SV.x1}" y1="${SV.y1}" y2="${SV.y1}" stroke="#111113" stroke-width="2"/>`
  g += `<line x1="${X(360)}" x2="${X(360)}" y1="${SV.y0 - 10}" y2="${SV.y1}" stroke="#111113" stroke-width="2" stroke-dasharray="8 8"/><text x="${X(360)}" y="${SV.y1 + 46}" text-anchor="middle" font-size="26" fill="#111113" font-weight="700">360 秒 · 预算</text>`
  g += `<rect id="ch-beam" x="${X(UPGRADE.x) - 22}" width="44" y="${SV.y0 - 20}" height="0" rx="22" fill="url(#beam)"/>`
  g += `<line id="ch-up" x1="${X(UPGRADE.x)}" x2="${X(UPGRADE.x)}" y1="${SV.y0 - 10}" y2="${SV.y1}" stroke="#FF4D1F" stroke-width="3" stroke-dasharray="10 8"/>`
  g += `<g id="ch-uptext"><text x="${X(UPGRADE.x) + 22}" y="${Y(45300)}" font-size="30" font-weight="700" fill="#111113">连续两次没进步</text><text x="${X(UPGRADE.x) + 22}" y="${Y(45300) + 40}" font-size="30" font-weight="700" fill="#FF4D1F">→ 换云端大模型</text></g>`
  g += `<line id="ch-head" y1="${SV.y0 - 10}" y2="${SV.y1}" stroke="#8E8D88" stroke-width="2"/>`
  g += `<path id="ch-path" fill="none" stroke="#111113" stroke-width="4" stroke-linejoin="round"/>`
  CANDS.forEach((c, i) => {
    const cx = X(c.x), cy = Y(c.y)
    const mark = c.m === 'x'
      ? `<g transform="translate(${cx} ${cy})"><g class="sc"><circle r="17" fill="#fff"/><path d="M-10 -10 L10 10 M10 -10 L-10 10" stroke="#111113" stroke-width="5" stroke-linecap="round"/></g></g>`
      : `<g transform="translate(${cx} ${cy})"><g class="sc"><circle r="15" fill="${c.m === 's' ? '#8E8D88' : '#FF4D1F'}" stroke="#fff" stroke-width="4"/></g></g>`
    const ly = c.pos === 'below' ? cy + 50 : cy - 28, anchor = c.pos === 'aboveEnd' ? 'end' : 'middle', lx = c.pos === 'aboveEnd' ? cx + 8 : cx
    g += `<g id="ch-c${i}">${mark}<text x="${lx}" y="${ly}" text-anchor="${anchor}" font-size="28" font-weight="700" fill="#111113">${c.label}</text></g>`
  })
  P.chart.innerHTML = `<div class="head"><div><div class="ttl">开发集得分<span>越高越好 · 横轴是已用时间（秒）</span></div>
    <div class="legend" style="margin-top:12px"><div><i style="background:#8E8D88"></i>本地小模型</div><div><i style="background:#FF4D1F"></i>云端大模型</div><div><b style="margin-right:10px">✕</b>被裁判拦下</div></div></div>
    <div class="best"><div class="num" id="ch-best">—</div><div class="who" id="ch-who"></div></div></div>
    <svg xmlns="${ns}" width="${SV.w - 80}" height="${SV.h}" viewBox="0 0 ${SV.w - 80} ${SV.h}" style="margin-top:6px"><defs><linearGradient id="beam" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#FF4D1F" stop-opacity="0"/><stop offset="1" stop-color="#FF4D1F" stop-opacity="0.55"/></linearGradient></defs>${g}</svg>`
}
P.result.innerHTML = `<div class="k">15 个从没见过的用例 · 只测一次 · 总能耗</div>
  <div class="pair"><div class="num muted">18,136</div><div class="arrow">→</div><div class="num" id="rs-n">18,136</div></div>
  <div class="pct num" id="rs-p">−0.0%</div><div class="foot" id="rs-f">15/15 全部通过 · 总分 139,972</div>`
P.routing.innerHTML = `<div class="rt"><div class="h">谁做决定</div><div class="h">得分提升（相对初始程序）</div><div class="h">用时</div>
  ${ROUTES.map(([a, b, g, s], i) => `<div class="lab rrow" data-i="${i}">${a}${b ? `<small>${b}</small>` : ''}</div>
    <div class="bar rrow" data-i="${i}"><b></b><span>+${g.toFixed(2)}%</span></div><div class="bar rrow" data-i="${i}"><b></b><span>${Math.round(s)} 秒</span></div>`).join('')}
  <div class="note">ahc026 · 四组同样的预算（360 秒 · 20 次请求 · 10 个候选），每组 1 次</div></div>`
const tile = (id, a, b) => `<div class="tile card"><div class="num" id="${id}">0</div><div class="a">${a}</div><div class="b">${b}</div></div>`
P.func.innerHTML = tile('fn-a', 'PageRank', '稀疏矩阵直接迭代') + tile('fn-b', '一维卷积', 'float32 实数 FFT')
P.ledger.innerHTML = tile('lg-a', '次交付', '全部通过最终测试') + tile('lg-b', '个候选', '通过外部裁判的验证') + tile('lg-c', '的时间', '花在等模型回复上')
P.end.innerHTML = '<div class="url card"><div class="a">在预算里做研究，每一步都有据可查</div><div class="b">github.com/bohack-2026-hw/QuotaCrux</div></div><div class="qr card"><img src="./data/qr.svg"></div>'
const routeRows = [...P.routing.querySelectorAll('.rrow')]

function brandAt(t) {
  letters.forEach((el, i) => {
    const g = easeOut(seg(t, 1.3 + i * 0.07, 1.9 + i * 0.07))
    el.style.transform = `translateY(${(1 - g) * 120}px)`
    el.style.opacity = g
  })
  cn.style.opacity = easeOut(seg(t, 2.2, 2.8))
  dot.style.transform = `scale(${easeOut(seg(t, 2.6, 3.0))})`
  // big and centred near the top, docks as a small badge in the corner, and comes back for the ending
  const d = ease(seg(t, 4.9, 5.9)) - ease(seg(t, 154.6, 155.8))
  const big = { x: 960 - 640, y: 70, s: 1 }, small = { x: 76, y: 52, s: 0.3 }
  brand.style.transform = `translate(${lerp(big.x, small.x, d)}px, ${lerp(big.y, small.y, d)}px) scale(${lerp(big.s, small.s, d)})`
}

function subAt(t) {
  const cur = SUBS.find(([a, b]) => t >= a && t < b)
  if (!cur) { sub.style.opacity = 0; return }
  const [a, b, text] = cur
  subText.textContent = text
  const g = easeOut(seg(t, a, a + 0.45))
  sub.style.opacity = Math.min(g, 1 - seg(t, b - 0.3, b))
  sub.style.transform = `translateY(${(1 - g) * 24}px)`
}

let tagKey = null
function tagAt(t) {
  const cur = TAGS.find(([a, b]) => t >= a && t < b)
  if (!cur) { tagEl.style.opacity = 0; return }
  const [a, b, n, k, v] = cur
  if (tagKey !== n) { tagEl.innerHTML = `<div class="k"><b>${n}</b>${k}</div><div class="v">${v}</div>`; tagKey = n }
  const g = easeOut(seg(t, a, a + 0.8))
  tagEl.style.opacity = Math.min(g, 1 - seg(t, b - 0.4, b))
  tagEl.style.transform = `translateY(${(1 - g) * 20}px)`
}

const project = (v) => { const p = v.clone().project(camera); return [(p.x + 1) / 2 * 1920, (1 - p.y) / 2 * 1080] }
const show = (el, o, extra = '') => { el.style.opacity = o; el.style.visibility = o > 0.001 ? 'visible' : 'hidden'; if (extra) el.style.transform = extra }

// ---------- camera ----------
function heightAround(R, p, span = 8, cap = Infinity) {
  let h = 0
  const k = Math.floor(p)
  for (let i = Math.max(0, k - span); i <= Math.min(R.states.length - 1, k + span); i++) {
    const w = 1 - Math.abs(i - p) / (span + 1)
    h = Math.max(h, R.H[i] * Math.max(0.6, w))
  }
  return Math.min(cap, Math.max(20, h))
}
function frame(h) {
  const top = h * BOX_H, d = Math.max(1, top / 9)
  return { pos: [-9 * d - 2.6, 4 + top * 0.95, 21 * d + 4], look: [-2.4, top * 0.42, 0] }
}
// a narrower, more frontal frame for one half of the split screen
function halfFrame(h) {
  const top = h * BOX_H, d = top * 2.1 + 16
  return { pos: [-0.16 * d, top * 0.45 + 5, d], look: [0, top * 0.36, 0] }
}
const LOOP_CAM = (t) => { const a = Math.sin(t * 0.07) * 0.22; return { pos: [Math.sin(a) * 13, 20.5, Math.cos(a) * 13], look: [0, 0, -0.9] } }
const mix = (A, B, g) => ({ pos: A.pos.map((v, i) => lerp(v, B.pos[i], g)), look: A.look.map((v, i) => lerp(v, B.look[i], g)) })
const orbit = (a, rad, y, ly) => ({ pos: [Math.sin(a) * rad, y, Math.cos(a) * rad], look: [0, ly, 0] })
function setCam(c) {
  camera.position.set(...c.pos); camera.lookAt(...c.look); camera.updateMatrixWorld()
  const d = camera.position.distanceTo(new THREE.Vector3(...c.look))
  scene.fog.near = d + 12; scene.fog.far = d + 70
}
function cameraAt(t, p) {
  if (t >= T.end[0]) {
    const a = ease(seg(t, T.end[0], T.end[1]))
    return setCam(orbit(lerp(0.95, 0.4, a), lerp(34, 31, a), lerp(10, 13, a), lerp(5.2, 5.8, a)))
  }
  if (t >= T.chart[0]) return setCam(LOOP_CAM(t))
  if (t >= 33.5) return setCam(mix(frame(20), LOOP_CAM(t), ease(seg(t, 34.6, 38.6))))
  // opening: a slow orbit from the right while the boxes land, settling into the 3/4 view
  const a = ease(seg(t, 0, 6.0))
  const open = orbit(lerp(0.95, -0.4, a), lerp(34, 30, a), lerp(10, 15, a), lerp(5.6, 6.2, a))
  const near = mix(open, frame(heightAround(R0, p, 8, 24)), ease(seg(t, 6.0, 10.5)))
  setCam(mix(near, frame(heightAround(R0, p, 40)), ease(seg(t, 21.5, 24.5))))
}

// ---------- render(t) ----------
const hotNow = new Set()
function applyHot(want) {
  for (const v of hotNow) if (!want.has(v)) { setHot(v, false); hotNow.delete(v) }
  for (const v of want) if (!hotNow.has(v)) { setHot(v, true); hotNow.add(v) }
}
function ringAt(t, st, on) {
  const left = st.flat()
  if (!left.length || !on) { ring.visible = false; return null }
  const next = Math.min(...left), si = st.findIndex((a) => a.includes(next))
  ring.visible = true
  ring.position.x = stackX(si)
  ring.material.opacity = on * (0.55 + 0.45 * Math.sin(t * 5))
  ring.scale.setScalar(1 + 0.12 * Math.sin(t * 5))
  return next
}
const isFast = (K, t) => { const dt = 0.05; return (pAt(K, t + dt) - pAt(K, t - dt)) / (2 * dt) > 3 }

function loopProps(t) {
  const on = t >= T.loop[0] && t < T.end[0] && !(t >= T.split[0] && t < T.routing[0] + 0.3)
  const vis = seg(t, 37.0, 39.0)
  for (const m of [tube, glow]) m.visible = t < T.end[0] + 1.2
  drawTube(t < T.end[0] ? ease(seg(t, 0.6, 3.2)) : 1 - ease(seg(t, T.end[0], T.end[0] + 1.2)))
  judge.visible = on && t >= 41.0
  judge.scale.setScalar(easeOut(seg(t, 41.0, 41.8)) || 0.001)
  const u = (stationU[0] + Math.max(0, t - CHIP.t0) / CHIP.period) % 1
  const q = loopCurve.getPointAt(u)
  chip.visible = chipGlow.visible = on && t >= CHIP.t0 - 0.5
  chip.position.set(q.x, 0.45 + Math.abs(Math.sin(t * 9)) * 0.08, q.z)
  chipGlow.position.copy(chip.position)
  chip.scale.setScalar(easeOut(seg(t, CHIP.t0 - 0.5, CHIP.t0)) || 0.001)
  const large = t >= CHIP.upgradeAt
  chip.material.color.set(large ? C.accent : 0x111113)
  chipGlow.material.opacity = large ? 0.3 : 0.12
  // stations light up as the chip passes; the judge flashes when the chip reaches 验证
  const loopUi = on && t < T.chart[0] + 0.6 ? fade(t, 37.6, T.chart[0] + 0.6, 0.6, 0.6) : 0
  STATIONS.forEach(([, x, z], i) => {
    const du = Math.min(Math.abs(u - stationU[i]), 1 - Math.abs(u - stationU[i]))
    const near = t >= CHIP.t0 && du < 0.035
    discs[i].material.color.set(near ? C.accent : 0x111113)
    discs[i].visible = on
    const el = stationEls[i], g = easeOut(seg(t, 38.2 + i * 0.35, 38.8 + i * 0.35))
    el.classList.toggle('on', near)
    const [sx, sy] = project(new THREE.Vector3(x, 0.1, z + (z > 0 ? 0.6 : -0.9)))
    el.style.left = `${sx}px`; el.style.top = `${sy + (z > 0 ? 18 : -30)}px`
    show(el, g * loopUi, `translate(-50%, -50%) translateY(${(1 - g) * 16}px)`)
  })
  const dv = Math.min(Math.abs(u - stationU[4]), 1 - Math.abs(u - stationU[4]))
  const flash = t >= CHIP.t0 && dv < 0.05
  judge.userData.edges.material.color.set(flash ? C.accent : 0x111113)
  const [jx, jy] = project(new THREE.Vector3(0, 0.95, 0))
  judgeEl.style.left = `${jx}px`; judgeEl.style.top = `${jy}px`
  show(judgeEl, easeOut(seg(t, 41.4, 42.0)) * loopUi)
  judgeEl.style.boxShadow = flash ? '0 0 0 4px #FF4D1F, 0 24px 60px -30px rgba(40,30,10,0.5)' : ''
  const [cx, cy] = project(new THREE.Vector3(q.x, 1.0, q.z))
  chipLabel.textContent = large ? '云端大模型' : '本地小模型'
  chipLabel.style.background = large ? C.accent : C.ink
  chipLabel.style.left = `${cx}px`; chipLabel.style.top = `${cy - 8}px`
  show(chipLabel, easeOut(seg(t, CHIP.t0, CHIP.t0 + 0.5)) * loopUi)
  show(budget, fade(t, 49.8, T.chart[0] + 0.6, 0.6, 0.6), `translateY(${(1 - easeOut(seg(t, 49.8, 50.4))) * 20}px)`)
}

function chartAt(t) {
  const px = pAt(KP, t)
  const acc = CANDS.filter((c) => c.m !== 'x' && t >= c.t)
  let d = '', best = null
  for (const c of acc) {
    if (best == null) d = `M${X(c.x)} ${Y(c.y)}`
    else d += ` H${X(c.x)} V${Y(Math.max(best, c.y))}`
    best = Math.max(best ?? -Infinity, c.y)
  }
  if (best != null && px > acc[acc.length - 1].x) d += ` H${X(px)}`
  $('ch-path').setAttribute('d', d || 'M0 0')
  $('ch-path').style.opacity = best == null ? 0 : 1
  const head = $('ch-head')
  head.setAttribute('x1', X(px)); head.setAttribute('x2', X(px))
  head.style.opacity = t < 88.4 ? 1 : 1 - seg(t, 88.4, 89.0)
  CANDS.forEach((c, i) => {
    const g = seg(t, c.t, c.t + 0.45), el = $(`ch-c${i}`)
    el.style.opacity = g > 0 ? 1 : 0
    const s = 1 + 2.7 * (g - 1) ** 3 + 1.7 * (g - 1) ** 2
    el.querySelector('.sc').setAttribute('transform', `scale(${Math.max(0.001, s)})`)
    el.querySelector('text').style.opacity = seg(t, c.t + 0.2, c.t + 0.6)
  })
  const bg = seg(t, UPGRADE.t, UPGRADE.t + 0.9)
  const beam = $('ch-beam')
  beam.setAttribute('height', (SV.y1 - SV.y0 + 20) * easeOut(bg))
  beam.style.opacity = 1 - seg(t, UPGRADE.t + 1.0, UPGRADE.t + 2.0)
  $('ch-up').style.opacity = seg(t, UPGRADE.t + 0.6, UPGRADE.t + 1.0)
  $('ch-uptext').style.opacity = seg(t, UPGRADE.t + 0.8, UPGRADE.t + 1.3)
  $('ch-best').textContent = best == null ? '—' : fmt(best)
  const large = t >= UPGRADE.t + 0.9
  $('ch-who').innerHTML = `<span class="${large ? 'acc' : 'muted'}">${large ? '云端大模型' : '本地小模型'}</span> · 这一轮最好 · 已用 ${Math.round(px)} / 360 秒`
}

function panelsAt(t) {
  const [ca, cb] = T.costCard
  show(P.cost, fade(t, ca, cb, 0.5, 0.5), `translate(-50%, -50%) scale(${0.94 + 0.06 * easeOut(seg(t, ca, ca + 0.5))})`)
  $('cost-n').textContent = fmt(18136 * ease(seg(t, ca + 0.3, ca + 1.8)))
  // the frosted backdrop: on for the chart, after the split replay, and through the closing cards
  const bgOn = Math.max(fade(t, T.chart[0], T.chart[1], 0.6, 0.6), fade(t, T.result[0], T.end[0] + 0.9, 0.5, 0.9))
  show(panel, bgOn)
  const pane = (el, [a, b], fi = 0.6, fo = 0.4) => { const g = fade(t, a, b, fi, fo); show(el, g, `translateY(${(1 - easeOut(seg(t, a, a + fi))) * 30}px)`); return g }
  if (pane(P.chart, [T.chart[0] + 0.2, T.chart[1]]) > 0) chartAt(t)
  const r = fade(t, T.result[0], T.result[1], 0.5, 0.4)
  show(P.result, r, `translate(-50%, -50%) scale(${0.94 + 0.06 * easeOut(seg(t, T.result[0], T.result[0] + 0.5))})`)
  if (r > 0) {
    const g = ease(seg(t, T.result[0] + 0.8, T.result[0] + 2.6))
    $('rs-n').textContent = fmt(lerp(18136, 10028, g))
    $('rs-p').textContent = `−${(44.7 * g).toFixed(1)}%`
    $('rs-f').style.opacity = seg(t, T.result[0] + 2.8, T.result[0] + 3.3)
  }
  if (pane(P.routing, T.routing) > 0) {
    const hot = t >= 114.6 && t < 120.6 ? 1 : t >= 120.8 && t < 126.6 ? 3 : t >= 126.8 ? 1 : -1
    routeRows.forEach((el) => {
      const i = +el.dataset.i
      el.classList.toggle('hot', i === hot)
      el.style.opacity = hot < 0 || i === hot ? 1 : 0.42
      const b = el.querySelector('b'), span = el.querySelector('span')
      if (!b) return
      const isTime = el.previousElementSibling.classList.contains('bar')
      const v = isTime ? ROUTES[i][3] / 520 : ROUTES[i][2] / 8
      const w = el.clientWidth * v * easeOut(seg(t, 115.0 + i * 0.35 + (isTime ? 0.2 : 0), 116.0 + i * 0.35 + (isTime ? 0.2 : 0)))
      b.style.width = `${w}px`; span.style.left = `${w + 16}px`
      span.style.opacity = seg(t, 115.6 + i * 0.35, 116.0 + i * 0.35)
    })
  }
  if (pane(P.func, T.func) > 0) {
    $('fn-a').innerHTML = `${(1 + 24 * ease(seg(t, 132.8, 134.4))).toFixed(1)}<small>×</small>`
    $('fn-b').innerHTML = `${(1 + 1.67 * ease(seg(t, 137.4, 138.6))).toFixed(2)}<small>×</small>`
    P.func.children[1].style.opacity = seg(t, 137.2, 137.7) * 0.75 + 0.25
  }
  if (pane(P.ledger, T.ledger) > 0) {
    $('lg-a').innerHTML = `${Math.round(15 * ease(seg(t, 142.8, 143.8)))}<small>/15</small>`
    $('lg-b').innerHTML = `${Math.round(60 * ease(seg(t, 144.4, 145.6)))}<small>/96</small>`
    $('lg-c').innerHTML = `${Math.round(94 * ease(seg(t, 148.4, 149.8)))}<small>%</small>`
    ;[142.6, 144.2, 148.2].forEach((a, i) => { P.ledger.children[i].style.opacity = seg(t, a, a + 0.5) * 0.8 + 0.2 })
  }
  show(P.end, seg(t, 156.4, 157.2), `translateY(${(1 - easeOut(seg(t, 156.4, 157.2))) * 30}px)`)
}

function renderSplit(t) {
  const f = pAt(KS, t), fast = true
  const sides = [[R0, f * R0.steps.length, 0], [R7, f * R7.steps.length, 960]]
  const drop = t - (T.split[0] + 0.2)
  const h = Math.max(heightAround(R0, sides[0][1], 30), heightAround(R7, sides[1][1], 30))
  camera.aspect = 960 / 1080; camera.updateProjectionMatrix()
  renderer.setScissorTest(true)
  const energies = []
  for (const [R, p, x] of sides) {
    const { energy, st } = placeReplay(R, p, t < T.split[0] + 3.5 ? drop : null, fast)
    energies.push(energy)
    ringAt(t, st, seg(t, 93.2, 93.8))
    setCam(halfFrame(h))
    renderer.setViewport(x, 0, 960, 1080); renderer.setScissor(x, 0, 960, 1080)
    renderer.render(scene, camera)
  }
  renderer.setScissorTest(false)
  renderer.setViewport(0, 0, 1920, 1080)
  camera.aspect = 1920 / 1080; camera.updateProjectionMatrix()
  return energies
}

window.render = (t) => {
  brandAt(t); tagAt(t); subAt(t); panelsAt(t)
  const split = t >= T.split[0] && t < T.routing[0] + 0.3
  show(divider, split ? fade(t, T.split[0], T.routing[0] + 0.3, 0.4, 0.3) : 0)
  pin.style.visibility = 'hidden'; delta.style.opacity = 0
  if (split) {
    applyHot(new Set())
    loopProps(t)
    const [e0, e7] = renderSplit(t)
    const g = fade(t, 93.0, T.routing[0], 0.6, 0.4)
    sideL.innerHTML = `<div class="k">累计能耗</div><div class="num">${fmt(e0)}</div><div class="who">初始程序</div>`
    sideR.innerHTML = `<div class="k">累计能耗</div><div class="num acc">${fmt(e7)}</div><div class="who">最终版本</div>`
    show(sideL, g); show(sideR, g); show(hud, 0)
    return
  }
  show(sideL, 0); show(sideR, 0)

  let p = 0, drop = null, fast = false, ringOn = 0
  if (t < T.split[0]) {
    p = pAt(K0, t); fast = isFast(K0, t)
    if (t < 4) drop = t
    ringOn = seg(t, 8.2, 8.8)
  } else if (t >= T.end[0]) {
    p = 0; drop = t - END_DROP
  } else p = R0.steps.length
  cameraAt(t, p)
  loopProps(t)
  const R = R0
  const { energy, move, st } = placeReplay(R, p, drop, fast)
  const next = ringAt(t, st, ringOn)
  const want = new Set()
  if (t >= 8.4 && next && t < T.split[0]) want.add(next)
  // box 8 callouts: buried by the very first move, then paid for at step 14
  const pinOn = Math.max(fade(t, 11.7, 14.8, 0.4, 0.4), fade(t, 18.9, 21.4, 0.4, 0.4))
  if (pinOn > 0 && st.flat().includes(8)) {
    want.add(8)
    const [x, y] = project(boxes.get(8).position.clone().add(new THREE.Vector3(0, 0.1, 0.5)))
    pin.innerHTML = t < 16 ? '箱子 <b>8</b> 被压在下面' : '当初压住 <b>8</b> 的一摞：<b>+29</b>'
    pin.style.left = `${x}px`; pin.style.top = `${y - 26}px`
    show(pin, pinOn)
  }
  applyHot(want)

  hud.innerHTML = `<div class="k">累计能耗</div><div class="v">${fmt(energy)}</div><div class="who">初始程序 · 这个用例</div>`
  show(hud, fade(t, 10.3, 36.9, 0.6, 0.5))
  if (move && move.f > 0.45 && !fast) {
    const [x, y] = project(move.land)
    const g = seg(move.f, 0.45, 1)
    delta.textContent = `+${move.s.k + 1}`
    delta.style.cssText = `left:${x}px;top:${y - g * 40}px;opacity:${Math.min(1, g * 3) * (1 - seg(move.f, 0.85, 1))}`
  }
  renderer.render(scene, camera)
}

// ---------- sound cues: derived from the same timeline, synthesised offline by sfx.py ----------
window.sfxEvents = () => {
  const ev = [], add = (t, type, o = {}) => ev.push({ t: +t.toFixed(4), type, gain: 0.5, pan: 0, ...o })
  letters.forEach((_, i) => add(1.45 + i * 0.07, 'tick', { gain: 0.16, f: 1800 + i * 90 }))
  add(2.6, 'chime', { gain: 0.42, f: [659.3, 987.8, 1318.5] })
  add(4.95, 'whoosh', { gain: 0.22, dur: 0.9 })
  const drops = (t0, gain) => replay.stacks.forEach((s, si) => s.forEach((_, j) => {
    const a = t0 + dropStart(si, j)
    add(a + 0.7 * 0.364, 'thud', { gain: gain * (0.7 + 0.3 * ((si * 7 + j * 3) % 5) / 4), pan: stackX(si) / 9 })
    add(a + 0.7 * 0.727, 'thud', { gain: gain * 0.25, pan: stackX(si) / 9 })
  }))
  drops(0, 0.13)
  drops(END_DROP, 0.1)
  drops(T.split[0] + 0.2, 0.07)
  TAGS.forEach(([a]) => add(a, 'whoosh', { gain: 0.14, dur: 0.6 }))
  add(8.25, 'blip', { gain: 0.3, f: 660 })
  const steps = (R, K, scale, pan, gainMul) => R.steps.forEach((s, k) => {
    const a = tAt(K, k / scale), b = tAt(K, (k + 1) / scale), dur = b - a
    if (dur > 0.25) {
      if (s.op === 'move') {
        add(a + dur * 0.08, 'whoosh', { gain: 0.2 * gainMul, dur: dur * 0.55, pan: pan + stackX(s.to) / 18 })
        add(a + dur * 0.5, 'tick', { gain: 0.3 * gainMul, f: 1500, pan })
        add(a + dur * 0.97, 'thud', { gain: Math.min(0.5, 0.18 + s.k * 0.015) * gainMul, pan: pan + stackX(s.to) / 18 })
      } else add(a + dur * 0.1, 'pop', { gain: 0.3 * gainMul, pan: pan + stackX(s.from) / 18 })
    } else if (s.op === 'move') add(a, 'tick', { gain: 0.09 * gainMul, f: 1300 + Math.min(900, s.k * 40), pan })
  })
  steps(R0, K0, 1, 0, 1)
  add(T.costCard[0], 'impact', { gain: 0.5 }); add(T.costCard[0] + 1.8, 'chime', { gain: 0.3, f: [523.3, 784] })
  add(36.9, 'whoosh', { gain: 0.25, dur: 1.4 })
  STATIONS.forEach((_, i) => add(38.3 + i * 0.35, 'blip', { gain: 0.22, f: [523.3, 587.3, 659.3, 784, 880, 1046.5][i] }))
  add(41.1, 'blip', { gain: 0.3, f: 392 })
  for (let n = 0; ; n++) {
    STATIONS.forEach((_, i) => {
      const du = (stationU[i] - stationU[0] + 1) % 1, at = CHIP.t0 + (n + du) * CHIP.period
      if (at > CHIP.t0 && at < T.chart[0]) add(at, i === 4 ? 'chime' : 'blip', i === 4 ? { gain: 0.16, f: [1046.5, 1568] } : { gain: 0.08, f: 1200 })
    })
    if (CHIP.t0 + n * CHIP.period > T.chart[0]) break
  }
  add(CHIP.upgradeAt, 'rise', { gain: 0.25, dur: 0.8 })
  add(49.8, 'blip', { gain: 0.25, f: 740 })
  add(T.chart[0], 'whoosh', { gain: 0.25, dur: 1.0 })
  CANDS.forEach((c, i) => {
    if (c.m === 's') add(c.t, 'blip', { gain: 0.35, f: i ? 330 : 392 })
    else if (c.m === 'x') add(c.t, 'buzz', { gain: 0.35 })
    else add(c.t, 'chime', { gain: i === 2 || i === 6 ? 0.45 : 0.28, f: i === 6 ? [784, 1174.7, 1568] : i === 2 ? [587.3, 880, 1174.7] : [880, 1318.5] })
  })
  add(60.3, 'blip', { gain: 0.25, f: 330 })
  add(UPGRADE.t, 'rise', { gain: 0.4, dur: 1.0 }); add(UPGRADE.t + 0.95, 'impact', { gain: 0.3 })
  add(T.split[0], 'whoosh', { gain: 0.3, dur: 1.2 })
  steps(R0, KS, R0.steps.length, -0.6, 0.8)
  steps(R7, KS, R7.steps.length, 0.6, 0.8)
  add(T.result[0], 'impact', { gain: 0.5 }); add(T.result[0] + 2.6, 'chime', { gain: 0.5, f: [523.3, 784, 1046.5, 1318.5] })
  add(T.routing[0], 'whoosh', { gain: 0.2, dur: 0.8 })
  ROUTES.forEach((_, i) => add(115.0 + i * 0.35, 'whoosh', { gain: 0.12, dur: 0.6, pan: -0.3 + i * 0.2 }))
  add(114.6, 'blip', { gain: 0.25, f: 880 }); add(120.8, 'blip', { gain: 0.25, f: 523.3 })
  add(132.8, 'impact', { gain: 0.35 }); add(134.4, 'chime', { gain: 0.3, f: [880, 1318.5] })
  add(137.4, 'impact', { gain: 0.3 }); add(138.6, 'chime', { gain: 0.25, f: [784, 1174.7] })
  ;[142.8, 144.4, 148.4].forEach((a) => add(a, 'impact', { gain: 0.35 }))
  add(T.end[0], 'whoosh', { gain: 0.3, dur: 1.2 })
  add(156.4, 'chime', { gain: 0.55, f: [523.3, 659.3, 784, 1046.5, 1568] })
  return ev.sort((a, b) => a.t - b.t)
}

window.render(0)
window.ready = true
