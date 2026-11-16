import { useCallback, useEffect, useRef, useState } from 'react'

/** Action asynchrone avec état de chargement et d'erreur. */
export function useAction() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true)
    setError(null)
    try { return await fn() } catch (e) { setError(e); return undefined } finally { setBusy(false) }
  }, [])
  return { busy, error, setError, run }
}

/** Chargement de données, relancé quand `deps` change ou via `reload()`. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [tick, setTick] = useState(0)
  const key = `${JSON.stringify(deps)}:${tick}`
  const [res, setRes] = useState<{ key: string; data: T | null; error: unknown }>({ key: '', data: null, error: null })
  const fnRef = useRef(fn)
  useEffect(() => { fnRef.current = fn })
  useEffect(() => {
    let alive = true
    fnRef.current()
      .then((data) => { if (alive) setRes({ key, data, error: null }) })
      .catch((error) => { if (alive) setRes((r) => ({ key, data: r.data, error })) })
    return () => { alive = false }
  }, [key])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  const setData = useCallback((data: T) => setRes((r) => ({ ...r, data })), [])
  return { data: res.data, error: res.error, loading: res.key !== key, reload, setData }
}

let toastTimer: number | undefined
export function toast(message: string, error = false) {
  document.querySelector('.toast')?.remove()
  const el = document.createElement('div')
  el.className = `toast${error ? ' error' : ''}`
  el.setAttribute('role', 'status')
  el.textContent = message
  document.body.appendChild(el)
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => el.remove(), 3800)
}
