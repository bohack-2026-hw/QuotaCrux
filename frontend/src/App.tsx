import { useEffect, useState } from 'react'
import { api } from './api'
import { usePoll } from './hooks'
import { useResearchBatch, useResearchList } from './researchData'
import { CompareView } from './views/CompareView'
import { ExperienceView } from './views/ExperienceView'
import { HomeView } from './views/HomeView'
import { LiveView } from './views/LiveView'
import { OverviewView } from './views/OverviewView'
import { ResearchView } from './views/ResearchView'
import { RunView } from './views/RunView'
import { VersionView } from './views/VersionView'

type Tab = 'home' | 'res' | 'run' | 'hist' | 'exp' | 'cmp' | 'ver' | 'live'

// Primary pages tell the within-task research story; minor pages keep the experience-phase records reachable.
const TABS: { id: Tab; lbl: string; minor?: boolean; title: string; en: string; desc: string; snapshot?: boolean }[] = [
  { id: 'home', lbl: '总览', title: '总览', en: 'overview', desc: '' },
  { id: 'res', lbl: '研究对照', title: '研究对照', en: 'within-task research', desc: '同一任务、同一预算上限，比较三种研究方式。' },
  { id: 'run', lbl: '运行', title: '运行', en: 'runs', desc: '每次运行的假设、实验与评测反馈。' },
  { id: 'hist', lbl: '经验阶段', minor: true, title: '经验阶段', en: 'experience phase', desc: '跨任务经验复用阶段的记录：任务流、分流器与留出对照。', snapshot: true },
  { id: 'exp', lbl: '经验', minor: true, title: '经验', en: 'experience', desc: '学习运行中经过评测的候选，及其条件、改动与实测结果。', snapshot: true },
  { id: 'cmp', lbl: '经验对照', minor: true, title: '经验对照', en: 'held-out comparison', desc: '同一批留出任务，只替换经验快照。', snapshot: true },
  { id: 'ver', lbl: '版本', minor: true, title: '版本', en: 'snapshots', desc: '不可变的经验快照；回退只切换后续运行读取的版本。', snapshot: true },
  { id: 'live', lbl: '实时', minor: true, title: '实时进度', en: 'live', desc: '正在运行的实验与机器负载，每 2 秒刷新。' },
]

type Theme = 'dark' | 'light'

/** ?theme=light|dark wins (for links and screenshots), then the viewer's last choice; storage may be unavailable. */
function initialTheme(): Theme {
  const q = new URLSearchParams(window.location.search).get('theme')
  if (q === 'light' || q === 'dark') return q
  try { return window.localStorage.getItem('routeevo.theme') === 'light' ? 'light' : 'dark' } catch { return 'dark' }
}

function readHash(): { tab: Tab; arg: string | null } {
  const [tab, arg] = window.location.hash.replace('#', '').split('/')
  return { tab: (TABS.some((t) => t.id === tab) ? tab : 'home') as Tab, arg: arg ?? null }
}

export default function App() {
  const [{ tab, arg }, setRoute] = useState(readHash)
  const [runId, setRunId] = useState<string | null>(tab === 'run' ? arg : null)
  const [snapshot, setSnapshot] = useState<string | null>(null)
  const [focusExp, setFocusExp] = useState<string | null>(null)
  const [theme, setTheme] = useState<Theme>(initialTheme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { window.localStorage.setItem('routeevo.theme', theme) } catch { /* per-viewer convenience only */ }
  }, [theme])
  const health = usePoll(api.health, [], 3000)
  const snaps = usePoll(api.snapshots, [], 5000)
  const active = snaps.data?.active_snapshot_id ?? 'v0'
  const activeRow = snaps.data?.snapshots.find((s) => s.snapshot_id === active)
  // The model shown is what the latest research batch actually ran, not a fixed label.
  const research = useResearchList()
  const latest = useResearchBatch(research.entries[0] ?? null).batch

  useEffect(() => {
    const on = () => { setRoute(readHash()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const go = (t: Tab, a?: string) => { window.location.hash = a ? `${t}/${a}` : t }

  const openRun = (id: string) => { setRunId(id); go('run', id) }
  const openExperience = (snap: string, exp?: string) => { setSnapshot(snap); setFocusExp(exp ?? null); go('exp') }
  const meta = TABS.find((t) => t.id === tab)!
  const running = !!health.data?.running_run_id

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="logo">R</span><span className="name">routeevo</span></div>
        <nav className="nav">
          {TABS.filter((t) => !t.minor).map((t) => (
            <button key={t.id} className={tab === t.id ? 'on' : ''} onClick={() => go(t.id)}>{t.lbl}</button>
          ))}
        </nav>
        <details className={`more ${meta.minor ? 'on' : ''}`} key={tab}>
          <summary>{meta.minor ? meta.lbl : '更多'} ▾</summary>
          <div className="menu">
            <div className="menu-cap">经验复用阶段</div>
            {TABS.filter((t) => t.minor).map((t) => (
              <button key={t.id} className={tab === t.id ? 'on' : ''} onClick={() => go(t.id)}>{t.lbl}</button>
            ))}
          </div>
        </details>
        <div className="status">
          {latest?.model?.name && <span className="model" title="最近研究批次使用的固定模型"><b>{latest.model.name}</b>{latest.model.hosted == null ? '' : latest.model.hosted ? ' · 托管' : ' · 本地'}</span>}
          {running && <span><span className="pulse" />运行中</span>}
          <button className="theme-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label={theme === 'dark' ? '切换到浅色' : '切换到深色'} title={theme === 'dark' ? '浅色（投影仪）' : '深色'}>{theme === 'dark' ? '☀' : '☾'}</button>
        </div>
      </header>
      <main>
        {tab !== 'home' && (
          <header className="masthead">
            <div>
              <h1>{meta.title}<span className="en">{meta.en}</span></h1>
              {meta.desc && <p>{meta.desc}</p>}
            </div>
            {meta.snapshot && (
              <div className="stamp" title="后续运行默认读取的经验快照">
                <div className="v">{active}</div>
                <div className="t">生效快照<b>{activeRow ? `${activeRow.experience_count} 条经验` : '—'}</b></div>
              </div>
            )}
          </header>
        )}
        {tab === 'home' && <HomeView onOpenResearch={(id) => go('res', id)} />}
        {tab === 'res' && <ResearchView selected={arg} onSelect={(id) => go('res', id)} onOpenRun={openRun} />}
        {tab === 'run' && <RunView runId={runId} setRunId={openRun} activeSnapshot={active} onOpenExperience={openExperience} />}
        {tab === 'hist' && <OverviewView onOpenRun={openRun} onOpenComparison={(id) => go('cmp', id)} />}
        {tab === 'exp' && <ExperienceView snapshotId={snapshot ?? active} setSnapshotId={setSnapshot} focus={focusExp} onOpenRun={openRun} />}
        {tab === 'cmp' && <CompareView selected={arg} onSelect={(id) => go('cmp', id)} onOpenRun={openRun} />}
        {tab === 'live' && <LiveView onOpenRun={openRun} onOpenComparison={(id) => go('cmp', id)} />}
        {tab === 'ver' && <VersionView onOpenSnapshot={(s) => openExperience(s)} onOpenRun={openRun} onChanged={() => snaps.refresh()} />}
      </main>
    </div>
  )
}
