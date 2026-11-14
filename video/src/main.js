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

// ---------- replay ----------
function buildReplay(steps) {
  const states = [replay.stacks.map((s) => s.slice())]
  for (const s of steps) {
    const st = states[states.length - 1].map((a) => a.slice())
    if (s.op === 'out') st[s.from].pop()
    else { const j = st[s.from].indexOf(s.v); const moved = st[s.from].splice(j); st[s.to].push(...moved) }
    states.push(st)
  }
  return { steps, states }
}
const R0 = buildReplay(replay.c0.steps)
const basePos = (st) => {
  const pos = new Map()
  st.forEach((stack, i) => stack.forEach((v, j) => pos.set(v, [stackX(i), BOX_H / 2 + j * BOX_H, 0])))
  return pos
}

/** Place boxes for replay progress p; `drop` (0..) animates the opening fall. Returns {energy, move} for overlays. */
function placeReplay(R, p, t, drop) {
  const n = R.steps.length
  const k = clamp(Math.floor(p), 0, n), f = k < n ? p - k : 0
  const st = R.states[k]
  const pos = basePos(st)
  for (const [v, mesh] of boxes) {
    const q = pos.get(v)
    mesh.visible = !!q
    if (!q) continue
    mesh.position.set(q[0], q[1], q[2]); mesh.scale.setScalar(1); mesh.rotation.set(0, 0, 0)
    if (drop) {
      const si = st.findIndex((a) => a.includes(v)), j = st[si].indexOf(v)
      const start = 0.15 + si * 0.07 + j * 0.05, g = seg(t, start, start + 0.7)
      mesh.visible = t >= start
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
      // dashed arc from the lifted block to its landing spot
      const a = new THREE.Vector3(x0, baseY, 0.6), b = new THREE.Vector3(x1, BOX_H / 2 + dstH * BOX_H, 0.6)
      const mid = new THREE.Vector3((x0 + x1) / 2, lift + 1.2, 0.6)
      trailGeo.setFromPoints(new THREE.QuadraticBezierCurve3(a, mid, b).getPoints(48))
      trail.computeLineDistances()
      trail.material.opacity = Math.sin(clamp(f) * Math.PI)
      trail.visible = true
      if (f > 0.5) energy = s.energy
      move = { s, f, land: new THREE.Vector3(x1, BOX_H / 2 + (dstH + moved.length) * BOX_H + 0.4, 0) }
    }
  }
  return { energy, move, k, st }
}

// ---------- overlays ----------
const $ = (id) => document.getElementById(id)
const brand = $('brand'), tagEl = $('tag'), hud = $('hud'), sub = $('sub'), subText = sub.querySelector('span'), delta = $('delta')
brand.innerHTML = `<div class="name">${[...'QuotaCrux'].map((ch) => `<span>${ch}</span>`).join('')}</div><div class="cn">枢决</div><div class="dot"></div>`
const letters = [...brand.querySelectorAll('.name span')], cn = brand.querySelector('.cn'), dot = brand.querySelector('.dot')
tagEl.innerHTML = '<div class="k"><b>01</b>测试难题</div><div class="v">AtCoder 启发式竞赛 · 搬箱子</div>'

const SUBS = [
  [0.9, 6.0, '让 AI 做研究，贵的往往不是算力，而是一次又一次的“再试一次”。'],
  [6.6, 10.6, '200 个箱子分在 10 堆里，必须按 1、2、3 的顺序，一个个搬出仓库。'],
  [10.8, 15.0, '要拿到下面的箱子，得先把上面一整摞搬走：搬 k 个箱子，耗 k+1 份力气。'],
]

function brandAt(t) {
  letters.forEach((el, i) => {
    const g = easeOut(seg(t, 1.3 + i * 0.07, 1.9 + i * 0.07))
    el.style.transform = `translateY(${(1 - g) * 120}px)`
    el.style.opacity = g
  })
  cn.style.opacity = easeOut(seg(t, 2.2, 2.8))
  dot.style.transform = `scale(${easeOut(seg(t, 2.6, 3.0))})`
  // big and centred near the top, then it docks as a small badge in the corner
  const d = ease(seg(t, 4.9, 5.9))
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

const project = (v) => { const p = v.clone().project(camera); return [(p.x + 1) / 2 * 1920, (1 - p.y) / 2 * 1080] }

// ---------- camera ----------
function heightAround(R, p, span = 8, cap = Infinity) {
  let h = 0
  const k = Math.floor(p)
  for (let i = Math.max(0, k - span); i <= Math.min(R.states.length - 1, k + span); i++) {
    const w = 1 - Math.abs(i - p) / (span + 1)
    h = Math.max(h, Math.max(...R.states[i].map((a) => a.length)) * Math.max(0.6, w))
  }
  return Math.min(cap, Math.max(20, h))
}
function frame(h) {
  const top = h * BOX_H, d = Math.max(1, top / 9)
  return { pos: [-9 * d - 2.6, 4 + top * 0.95, 21 * d + 4], look: [-2.4, top * 0.42, 0] }
}
function cameraAt(t, R, p) {
  // opening: a slow orbit from the right while the boxes land, settling into the 3/4 view
  const a = ease(seg(t, 0, 6.0))
  const ang = lerp(0.95, -0.4, a), rad = lerp(34, 30, a)
  const open = { pos: [Math.sin(ang) * rad, lerp(10, 15, a), Math.cos(ang) * rad], look: [0, lerp(5.6, 6.2, a), 0] }
  const fr = frame(heightAround(R, p, 8, 24))
  const g = ease(seg(t, 6.0, 10.5))
  camera.position.set(...open.pos.map((v, i) => lerp(v, fr.pos[i], g)))
  camera.lookAt(...open.look.map((v, i) => lerp(v, fr.look[i], g)))
}

// ---------- render(t) ----------
const REPLAY_START = 10.8, STEP_S = 0.62
window.DURATION = 15
window.render = (t) => {
  const p = t < REPLAY_START ? 0 : (t - REPLAY_START) / STEP_S
  cameraAt(t, R0, p)
  drawTube(ease(seg(t, 0.6, 3.2)))
  const { energy, move, st } = placeReplay(R0, p, t, t < 4)
  // the next box to carry out, and the stack that holds it
  const next = Math.min(...st.flat())
  for (const v of [1, next]) setHot(v, t >= 8.4 && v === next)
  const si = st.findIndex((a) => a.includes(next))
  ring.position.x = stackX(si)
  ring.material.opacity = seg(t, 8.2, 8.8) * (0.55 + 0.45 * Math.sin(t * 5))
  ring.scale.setScalar(1 + 0.12 * Math.sin(t * 5))

  brandAt(t)
  tagEl.style.opacity = easeOut(seg(t, 6.0, 6.8))
  tagEl.style.transform = `translateY(${(1 - easeOut(seg(t, 6.0, 6.8))) * 20}px)`
  subAt(t)
  hud.innerHTML = `<div class="k">累计能耗</div><div class="v">${energy}</div><div class="who">初始程序</div>`
  hud.style.opacity = seg(t, 10.3, 10.9)
  if (move && move.f > 0.45) {
    const [x, y] = project(move.land)
    const g = seg(move.f, 0.45, 1)
    delta.textContent = `+${move.s.k + 1}`
    delta.style.cssText = `left:${x}px;top:${y - g * 40}px;opacity:${Math.min(1, g * 3) * (1 - seg(move.f, 0.85, 1))}`
  } else delta.style.opacity = 0
  renderer.render(scene, camera)
}
window.render(0)
window.ready = true
