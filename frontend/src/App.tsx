import { useEffect, useState } from 'react'
import { api } from './api'
import { usePoll } from './hooks'
import { CompareView } from './views/CompareView'
import { OverviewView } from './views/OverviewView'
import { ExperienceView } from './views/ExperienceView'
import { RunView } from './views/RunView'
import { VersionView } from './views/VersionView'
import { LiveView } from './views/LiveView'
import { ResearchView } from './views/ResearchView'
import { useResearchBatch, useResearchList } from './researchData'

type Tab = 'home' | 'res' | 'run' | 'exp' | 'cmp' | 'ver' | 'live'

const TABS: { id: Tab; num: string; lbl: string; sub: string; title: string; en: string; desc: string }[] = [
  { id: 'home', num: '00', lbl: '总览', sub: '研究进展 · 历史成果', title: '总览', en: 'Research Agent',
    desc: '单个长任务内持续研究与优化：模型、提示、预算与评测器固定，比较看得到反馈、彼此独立、看不到反馈三种研究方式。开发集改善与最终集验收分开呈现；跨任务经验阶段的记录保留在下方。' },
  { id: 'res', num: '01', lbl: '研究对照', sub: '反馈 · 独立 · 无反馈', title: '研究对照', en: 'Within-task research',
    desc: '同一任务、同一预算上限下，按重复配对三组研究方式：开发集最佳结果随墙钟、Token 与费用的变化，最终集状态，以及实际消耗。未测、失败、零提升与改善分别标出。' },
  { id: 'run', num: '02', lbl: '研究运行', sub: '证据 · 假设 · 实验', title: '研究运行', en: 'Research run',
    desc: '研究问题、基线、工具与预算在开始前固定；Agent 取证、提出假设并做实验，固定评测器给出判定，反馈决定下一步。每一步的目的、预期与实际结果都记录在案。' },
  { id: 'exp', num: '03', lbl: '经验查看', sub: '已验证的执行事实', title: '经验', en: 'Verified experience',
    desc: '经验来自学习运行中经过评测的候选：在什么条件下、做了什么改动、实测结果如何、证据在哪里。模型解释单独标为未验证。' },
  { id: 'cmp', num: '04', lbl: '经验对照', sub: '旧经验 vs 新经验', title: '经验对照', en: 'Held-out comparison',
    desc: '同一批未参与学习的任务、同一配置，只替换经验快照，串行交替运行并保留全部结果，包括失败与无收益。' },
  { id: 'ver', num: '05', lbl: '版本管理', sub: '快照 · 差异 · 回退', title: '版本', en: 'Snapshots & rollback',
    desc: '每次学习发布一个不可变快照；回退只切换后续运行读取的版本，历史记录全部保留。' },
  { id: 'live', num: '06', lbl: '实时进度', sub: '正在做什么 · 实验进度', title: '实时进度', en: 'Live progress',
    desc: '工作计划与日志、正在运行的实验（逐任务、逐次重放）、正在执行的运行和机器负载，每 2 秒刷新。' },
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
  // The model line names what the latest research batch actually ran, not a fixed label.
  const research = useResearchList()
  const latest = useResearchBatch(research.entries[0] ?? null).batch

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
          <div title={latest ? `最近研究批次 ${latest.id}` : undefined}>
            {latest?.model?.name ? `研究模型：${latest.model.name}${latest.model.hosted == null ? '' : latest.model.hosted ? '（托管）' : '（本地）'} · 固定` : '模型以每次运行记录为准'}
          </div>
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
        {tab === 'home' && <OverviewView onOpenRun={openRun} onOpenComparison={(id) => go('cmp', id)} onOpenResearch={(id) => go('res', id)} />}
        {tab === 'res' && <ResearchView selected={arg} onSelect={(id) => go('res', id)} onOpenRun={openRun} />}
        {tab === 'run' && <RunView runId={runId} setRunId={openRun} activeSnapshot={active} onOpenExperience={openExperience} />}
        {tab === 'exp' && <ExperienceView snapshotId={snapshot ?? active} setSnapshotId={setSnapshot} focus={focusExp} onOpenRun={openRun} />}
        {tab === 'cmp' && <CompareView selected={arg} onSelect={(id) => go('cmp', id)} onOpenRun={openRun} />}
        {tab === 'live' && <LiveView onOpenRun={openRun} onOpenComparison={(id) => go('cmp', id)} />}
        {tab === 'ver' && <VersionView onOpenSnapshot={(s) => openExperience(s)} onOpenRun={openRun} onChanged={() => snaps.refresh()} />}
      </main>
    </div>
  )
}
