import { useEffect, useState } from 'react'
import { api } from './api'
import { usePoll } from './hooks'
import { CompareView } from './views/CompareView'
import { OverviewView } from './views/OverviewView'
import { ExperienceView } from './views/ExperienceView'
import { RunView } from './views/RunView'
import { VersionView } from './views/VersionView'

type Tab = 'home' | 'run' | 'exp' | 'cmp' | 'ver'

const TABS: { id: Tab; num: string; lbl: string; sub: string; title: string; en: string; desc: string }[] = [
  { id: 'home', num: '00', lbl: '总览', sub: '学到什么 · 是否更好', title: '总览', en: 'Does experience help?',
    desc: '模型、提示词、预算与评测全部固定，只有经验快照在变化。下面是学习过程、留出任务上的对照结果，以及由数据自动生成的进化说明。' },
  { id: 'run', num: '01', lbl: '任务运行', sub: '决策 · 执行 · 验证', title: '任务运行', en: 'Run ledger',
    desc: '给定任务、预算与经验快照，Agent 选择行动，程序执行并由固定评测器验证；每一步的目的、预期与实际反馈都记录在案。' },
  { id: 'exp', num: '02', lbl: '经验查看', sub: '已验证的执行事实', title: '经验', en: 'Verified experience',
    desc: '经验来自学习运行中经过评测的候选：在什么条件下、做了什么改动、实测结果如何、证据在哪里。模型解释单独标为未验证。' },
  { id: 'cmp', num: '03', lbl: '对照结果', sub: '旧经验 vs 新经验', title: '对照', en: 'Held-out comparison',
    desc: '同一批未参与学习的任务、同一配置，只替换经验快照，串行交替运行并保留全部结果，包括失败与无收益。' },
  { id: 'ver', num: '04', lbl: '版本管理', sub: '快照 · 差异 · 回退', title: '版本', en: 'Snapshots & rollback',
    desc: '每次学习发布一个不可变快照；回退只切换后续运行读取的版本，历史记录全部保留。' },
]

function readHash(): { tab: Tab; arg: string | null } {
  const [tab, arg] = window.location.hash.replace('#', '').split('/')
  return { tab: (TABS.some((t) => t.id === tab) ? tab : 'home') as Tab, arg: arg ?? null }
}

export default function App() {
  const [{ tab, arg }, setRoute] = useState(readHash)
  const [runId, setRunId] = useState<string | null>(tab === 'run' ? arg : null)
  const [snapshot, setSnapshot] = useState<string | null>(null)
  const [focusExp, setFocusExp] = useState<string | null>(null)
  const health = usePoll(api.health, [], 3000)
  const snaps = usePoll(api.snapshots, [], 3000)
  const active = snaps.data?.active_snapshot_id ?? 'v0'
  const activeRow = snaps.data?.snapshots.find((s) => s.snapshot_id === active)

  useEffect(() => {
    const on = () => setRoute(readHash())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const go = (t: Tab, a?: string) => { window.location.hash = a ? `${t}/${a}` : t }

  const openRun = (id: string) => { setRunId(id); go('run', id) }
  const openExperience = (snap: string, exp?: string) => { setSnapshot(snap); setFocusExp(exp ?? null); go('exp') }
  const meta = TABS.find((t) => t.id === tab)!

  return (
    <div className="app">
      <aside className="rail">
        <div className="brand">
          <div className="brand-name">Route<em>Evo</em></div>
          <div className="brand-sub">进化实验记录本</div>
        </div>
        <nav className="nav">
          {TABS.map((t) => (
            <button key={t.id} className={tab === t.id ? 'on' : ''} onClick={() => go(t.id)}>
              <span className="num">{t.num}</span>
              <span className="lbl">{t.lbl}<small>{t.sub}</small></span>
            </button>
          ))}
        </nav>
        <div className="rail-foot">
          <div><span className={`pulse ${health.data?.running_run_id ? '' : 'idle'}`} />{health.data?.running_run_id ? '有运行在执行' : '空闲'}</div>
          <div>Qwen（本地）→ GPT-6.1 Sol（xhigh）</div>
          <div>Docker 沙箱 · 外部评测器</div>
          {health.error && <div style={{ color: 'var(--accent)' }}>后端未连接</div>}
        </div>
      </aside>
      <main>
        <header className="masthead">
          <div>
            <h1>{meta.title}<span className="en">{meta.en}</span></h1>
            <p>{meta.desc}</p>
          </div>
          <div className="stamp" title="后续运行默认读取的经验快照">
            <div className="v">{active}</div>
            <div className="t">生效经验版本<b>{activeRow ? `${activeRow.experience_count} 条经验` : '—'}</b></div>
          </div>
        </header>
        {tab === 'home' && <OverviewView onOpenRun={openRun} onOpenComparison={(id) => go('cmp', id)} />}
        {tab === 'run' && <RunView runId={runId} setRunId={openRun} activeSnapshot={active} onOpenExperience={openExperience} />}
        {tab === 'exp' && <ExperienceView snapshotId={snapshot ?? active} setSnapshotId={setSnapshot} focus={focusExp} onOpenRun={openRun} />}
        {tab === 'cmp' && <CompareView selected={arg} onSelect={(id) => go('cmp', id)} onOpenRun={openRun} />}
        {tab === 'ver' && <VersionView onOpenSnapshot={(s) => openExperience(s)} onOpenRun={openRun} onChanged={() => snaps.refresh()} />}
      </main>
    </div>
  )
}
