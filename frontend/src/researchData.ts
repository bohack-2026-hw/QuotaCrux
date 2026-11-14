// Where research batches come from: the read-only API from #2 when it exists, plus the archived batches committed under
// docs/research (real runs, exported by scripts/research-sample.mjs). Nothing here starts or changes an experiment.
import { useMemo } from 'react'
import { api } from './api'
import { usePoll } from './hooks'
import { normalize } from './research'
import type { RawBatch, RBatch } from './research'
import archivedR2 from './samples/research-native-r2.json'

export interface BatchEntry {
  id: string; label: string | null; status: string; createdAt: string | null
  source: 'api' | 'archive'; archivePath: string | null
}

const ARCHIVE: RawBatch[] = [archivedR2 as RawBatch]
export const REPO_BLOB = 'https://github.com/bohack-2026-hw/RouteEvo/blob/main/'

export type ApiState = 'ok' | 'missing' | 'error' | 'loading'

export function useResearchList() {
  const res = usePoll(async () => {
    try {
      return { rows: await api.researchComparisons(), state: 'ok' as ApiState, error: null as string | null }
    } catch (e) {
      const msg = (e as Error).message
      return { rows: [], state: (/not found|404/i.test(msg) ? 'missing' : 'error') as ApiState, error: msg }
    }
  }, [], 10000)
  const entries = useMemo<BatchEntry[]>(() => {
    const live: BatchEntry[] = (res.data?.rows ?? [])
      .map((r) => ({ id: r.comparison_id, label: r.label ?? null, status: r.status, createdAt: r.created_at ?? null, source: 'api' as const, archivePath: null }))
      .sort((a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? ''))
    const archived: BatchEntry[] = ARCHIVE.filter((a) => !live.some((l) => l.id === a.comparison_id)).map((a) => ({
      id: a.comparison_id, label: a.label ?? null, status: a.status, createdAt: a.created_at ?? null,
      source: 'archive' as const, archivePath: a.source?.path ?? null,
    }))
    return [...live, ...archived]
  }, [res.data])
  return { entries, apiState: (res.data?.state ?? 'loading') as ApiState, apiError: res.data?.error ?? null }
}

/** One batch, normalized. API batches poll while running; archived batches never change. */
export function useResearchBatch(entry: BatchEntry | null): { batch: RBatch | null; error: string | null } {
  const isApi = entry?.source === 'api'
  const live = usePoll(() => (entry && isApi ? api.researchComparison(entry.id) : Promise.resolve(null)), [entry?.id, isApi], 5000,
    isApi && entry?.status === 'running')
  const archived = useMemo(() => {
    const raw = entry && !isApi ? ARCHIVE.find((a) => a.comparison_id === entry.id) : null
    return raw ? normalize(raw) : null
  }, [entry, isApi])
  const fromApi = useMemo(() => (live.data ? normalize(live.data) : null), [live.data])
  return { batch: isApi ? fromApi : archived, error: isApi ? live.error : null }
}
