import { useCallback, useEffect, useRef, useState } from 'react'

/** Fetch once and re-fetch every `ms` while `live` is true. Keeps the previous value during refetch (no flash). */
export function usePoll<T>(fn: () => Promise<T>, deps: unknown[], ms = 2000, live = true) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const refresh = useCallback(async () => {
    try {
      setData(await fnRef.current())
      setError(null)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    let alive = true
    const tick = async () => { if (alive) await refresh() }
    tick()
    if (!live) return () => { alive = false }
    const id = setInterval(tick, ms)
    return () => { alive = false; clearInterval(id) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, live, ms])

  return { data, error, refresh }
}

/** Rendered pixel width of an element, so SVG charts draw at true size instead of scaling their text. */
export function useWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(fallback)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(320, Math.floor(entry.contentRect.width))))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}
