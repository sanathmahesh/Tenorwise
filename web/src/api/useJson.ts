import { useEffect, useState } from 'react'

export type Loaded<T> = { state: 'loading' } | { state: 'ok'; data: T } | { state: 'error'; error: string }

/** Fetch a static snapshot file, e.g. useJson<Curve>('curve.json'). */
export function useJson<T>(file: string): Loaded<T> {
  const [result, setResult] = useState<Loaded<T>>({ state: 'loading' })
  useEffect(() => {
    fetch(`/data/v1/${file}`)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        setResult({ state: 'ok', data: (await r.json()) as T })
      })
      .catch((e: unknown) => setResult({ state: 'error', error: String(e) }))
  }, [file])
  return result
}
