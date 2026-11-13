import type { ReactNode } from 'react'
import type { Tone } from '../labels'
import { status } from '../labels'

export function Chip({ tone = 'neutral', icon, children }: { tone?: Tone; icon?: string; children: ReactNode }) {
  const cls = tone === 'good' ? 'good' : tone === 'bad' ? 'bad' : tone === 'warn' ? 'warn' : tone === 'accent' ? 'accent' : ''
  return <span className={`chip ${cls}`}>{icon && <span aria-hidden>{icon}</span>}{children}</span>
}

const ICON: Record<Tone, string> = { good: '✓', bad: '✕', warn: '!', neutral: '', accent: '●' }

export function StatusChip({ value }: { value: string | null | undefined }) {
  const [label, tone] = status(value)
  return <Chip tone={tone} icon={ICON[tone] || undefined}>{label}</Chip>
}

export function Meter({ label, value, max, unit, hot }: { label: string; value: number; max: number; unit?: string; hot?: boolean }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className={`meter ${hot ? 'hot' : ''}`}>
      <div className="top">
        <span className="k">{label}</span>
        <span className="v">{Number.isInteger(value) ? value : value.toFixed(1)}<small> / {max}{unit}</small></span>
      </div>
      <div className="track" role="meter" aria-valuemin={0} aria-valuemax={max} aria-valuenow={value} aria-label={label}>
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function Stat({ k, v, s }: { k: string; v: ReactNode; s?: ReactNode }) {
  return (
    <div className="stat">
      <div className="k">{k}</div>
      <div className="v">{v}</div>
      {s != null && <div className="s">{s}</div>}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return <div className="empty"><b>{title}</b>{children}</div>
}

export function DiffView({ diff }: { diff: string }) {
  return (
    <pre className="code">
      {diff.split('\n').map((line, i) => {
        const cls = line.startsWith('@@') ? 'hunk' : line.startsWith('+') && !line.startsWith('+++') ? 'add'
          : line.startsWith('-') && !line.startsWith('---') ? 'del' : undefined
        return cls ? <span key={i} className={cls}>{line}</span> : <span key={i}>{line}{'\n'}</span>
      })}
    </pre>
  )
}
