// QuotaCrux 枢决 showcase video. Everything on screen is a pure function of time t (seconds): window.render(t).
import * as THREE from 'three'

const C = { bg: 0xF3F2EE, ink: '#111113', grey: '#8E8D88', accent: '#FF4D1F', card: '#D8BC92', cardEdge: '#B8976A' }
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v))
const seg = (t, a, b) => clamp((t - a) / (b - a))
const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2)
const lerp = (a, b, f) => a + (b - a) * f

// ---------- data ----------
const replay = await (await fetch('./data/replay.json')).json()
const N = 200, M = 10, BOX_H = 0.4, GAP_X = 1.4

// ---------- three.js scene ----------
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('gl'), antialias: true, preserveDrawingBuffer: true })
renderer.setPixelRatio(1)
renderer.setSize(1920, 1080, false)
renderer.shadowMap.enabled = true
renderer.shadowMap.type = THREE.PCFSoftShadowMap
renderer.outputColorSpace = THREE.SRGBColorSpace
const scene = new THREE.Scene()
scene.background = new THREE.Color(C.bg)
scene.fog = new THREE.Fog(C.bg, 40, 80)
const camera = new THREE.PerspectiveCamera(32, 1920 / 1080, 0.1, 200)

scene.add(new THREE.HemisphereLight(0xffffff, 0xd8d2c6, 1.6))
const sun = new THREE.DirectionalLight(0xffffff, 2.2)
sun.position.set(-8, 18, 14)
sun.castShadow = true
sun.shadow.mapSize.set(2048, 2048)
Object.assign(sun.shadow.camera, { left: -14, right: 14, top: 16, bottom: -4, near: 1, far: 60 })
scene.add(sun)
const floor = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.MeshStandardMaterial({ color: 0xE6E3DB, roughness: 1 }))
floor.rotation.x = -Math.PI / 2
floor.receiveShadow = true
scene.add(floor)
// stack slots drawn on the floor
for (let i = 0; i < M; i++) {
  const slot = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 1.1), new THREE.MeshBasicMaterial({ color: 0xD8D4CA }))
  slot.rotation.x = -Math.PI / 2
  slot.position.set(stackX(i), 0.002, 0)
  scene.add(slot)
}

function stackX(i) { return (i - (M - 1) / 2) * GAP_X }

function labelTexture(n, hot) {
  const c = document.createElement('canvas')
  c.width = 256; c.height = 128
  const g = c.getContext('2d')
  g.fillStyle = hot ? C.accent : C.card
  g.fillRect(0, 0, 256, 128)
  g.strokeStyle = hot ? '#C93A12' : C.cardEdge
  g.lineWidth = 6
  g.strokeRect(3, 3, 250, 122)
  g.fillStyle = hot ? '#ffffff' : C.ink
  g.font = '800 78px "Avenir Next", sans-serif'
  g.textAlign = 'center'; g.textBaseline = 'middle'
  g.fillText(String(n), 128, 70)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 4
  return tex
}

const boxGeo = new THREE.BoxGeometry(1.0, BOX_H * 0.94, 0.92)
const sideMat = new THREE.MeshStandardMaterial({ color: 0xC9AA7C, roughness: 0.9 })
const topMat = new THREE.MeshStandardMaterial({ color: 0xD2B386, roughness: 0.9 })
const boxes = new Map()
for (let v = 1; v <= N; v++) {
  const front = new THREE.MeshStandardMaterial({ map: labelTexture(v, false), roughness: 0.85 })
  const mesh = new THREE.Mesh(boxGeo, [sideMat, sideMat, topMat, sideMat, front, sideMat])
  mesh.castShadow = true; mesh.receiveShadow = true
  mesh.userData = { front, plain: front.map, hot: null }
  scene.add(mesh)
  boxes.set(v, mesh)
}
function setHot(v, on) {
  const m = boxes.get(v).userData
  if (on && !m.hot) m.hot = labelTexture(v, true)
  m.front.map = on ? m.hot : m.plain
  m.front.needsUpdate = true
}

// ---------- replay: states after each step, interpolated moves ----------
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

function basePos(st) {
  const pos = new Map()
  st.forEach((stack, i) => stack.forEach((v, j) => pos.set(v, [stackX(i), BOX_H / 2 + j * BOX_H, 0])))
  return pos
}

/** Place all boxes for replay progress p (steps done + fraction of the next step). Returns energy shown. */
function placeReplay(R, p) {
  const n = R.steps.length
  const k = clamp(Math.floor(p), 0, n), f = k < n ? p - k : 0
  const st = R.states[k]
  const pos = basePos(st)
  for (const [v, mesh] of boxes) {
    const q = pos.get(v)
    mesh.visible = !!q
    if (q) { mesh.position.set(q[0], q[1], q[2]); mesh.scale.setScalar(1) }
  }
  let energy = k > 0 ? R.steps[k - 1].energy : 0
  if (k < n && f > 0) {
    const s = R.steps[k], e = ease(f)
    if (s.op === 'out') {
      const mesh = boxes.get(s.v), q = pos.get(s.v)
      mesh.position.set(q[0], q[1] + Math.sin(e * Math.PI) * 0.8, q[2] + e * 6)
      mesh.scale.setScalar(1 - 0.6 * e)
    } else {
      const src = st[s.from], j = src.indexOf(s.v), moved = src.slice(j)
      const dstH = st[s.to].length
      const lift = Math.max(src.length, dstH) * BOX_H + 1.0
      moved.forEach((v, idx) => {
        const from = pos.get(v)
        const to = [stackX(s.to), BOX_H / 2 + (dstH + idx) * BOX_H, 0]
        const y0 = from[1], y1 = to[1], top = lift + idx * BOX_H
        let x, y
        if (f < 0.3) { const g = ease(f / 0.3); x = from[0]; y = lerp(y0, top, g) }
        else if (f < 0.7) { const g = ease((f - 0.3) / 0.4); x = lerp(from[0], to[0], g); y = top }
        else { const g = ease((f - 0.7) / 0.3); x = to[0]; y = lerp(top, y1, g) }
        boxes.get(v).position.set(x, y, 0)
      })
      if (f > 0.5) energy = s.energy
    }
  }
  return energy
}

// ---------- overlays ----------
const $ = (id) => document.getElementById(id)
const titleEl = $('title'), subEl = $('sub'), hudEl = $('hud'), tagEl = $('tag')
titleEl.innerHTML = `<svg viewBox="0 0 1920 1080" width="1920" height="1080"><path id="loop" d="M 520 300 H 1400 A 140 140 0 0 1 1540 440 V 640 A 140 140 0 0 1 1400 780 H 520 A 140 140 0 0 1 380 640 V 440 A 140 140 0 0 1 520 300 Z" fill="none" stroke="${C.accent}" stroke-width="10" stroke-linecap="round"/></svg>
  <div class="name">QuotaCrux</div><div class="cn">枢决</div>`
const loop = titleEl.querySelector('#loop'), loopLen = loop.getTotalLength()
loop.style.strokeDasharray = `${loopLen}`

const SUBS = [
  [0.6, 6.0, '让 AI 做研究，贵的往往不是算力，而是一次又一次的“再试一次”。'],
  [6.6, 10.6, '测试难题：200 个箱子分在 10 堆里，必须按 1、2、3 的顺序，一个个搬出仓库。'],
  [10.8, 15.0, '要拿到下面的箱子，得先把上面一整摞搬走：搬 k 个箱子，耗 k+1 份力气。'],
]

function overlays(t) {
  // title: the loop draws itself, the name settles in, then everything gives way to the warehouse
  const show = 1 - seg(t, 5.0, 6.0)
  titleEl.style.opacity = show
  titleEl.style.display = show > 0 ? 'flex' : 'none'
  loop.style.strokeDashoffset = `${loopLen * (1 - ease(seg(t, 0.2, 2.4)))}`
  const nameIn = ease(seg(t, 1.6, 3.0))
  titleEl.querySelector('.name').style.cssText = `opacity:${nameIn};transform:translateY(${(1 - nameIn) * 30}px)`
  const cnIn = ease(seg(t, 2.4, 3.6))
  titleEl.querySelector('.cn').style.cssText = `opacity:${cnIn}`

  const sub = SUBS.find(([a, b]) => t >= a && t < b)
  if (sub) {
    const [a, b, text] = sub
    subEl.textContent = text
    subEl.style.opacity = Math.min(seg(t, a, a + 0.3), 1 - seg(t, b - 0.3, b))
  } else subEl.style.opacity = 0

  const tagIn = seg(t, 6.4, 7.2)
  tagEl.innerHTML = '<div class="k">测试难题</div><div class="v">AtCoder 启发式竞赛 · 搬箱子</div>'
  tagEl.style.opacity = tagIn
}

// ---------- camera ----------
// Framing follows the replay: the tallest stack within a few steps either side sets distance and aim, smoothed so the
// camera glides instead of jumping. Pure function of (replay, progress).
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
  return { pos: [-9 * d, 4 + top * 0.95, 21 * d + 4], look: [0.6, top * 0.42, 0] }
}
function cameraAt(t, R, p) {
  const intro = ease(seg(t, 5.0, 10.5))
  const wide = { pos: [-2, 22, 44], look: [0, 3.5, 0] }
  const fr = frame(heightAround(R, p, 8, 24))
  camera.position.set(...wide.pos.map((v, i) => lerp(v, fr.pos[i], intro)))
  camera.lookAt(...wide.look.map((v, i) => lerp(v, fr.look[i], intro)))
}

// ---------- render(t) ----------
const REPLAY_START = 10.8, STEP_S = 0.62
window.DURATION = 15
window.render = (t) => {
  const p = t < REPLAY_START ? 0 : (t - REPLAY_START) / STEP_S
  cameraAt(t, R0, p)
  overlays(t)
  setHot(1, t >= 8.4)
  const energy = placeReplay(R0, p)
  hudEl.innerHTML = `<div class="k">能耗</div><div class="v">${energy}</div>`
  hudEl.style.opacity = seg(t, 10.4, 10.9)
  renderer.render(scene, camera)
}
window.render(0)
window.ready = true
