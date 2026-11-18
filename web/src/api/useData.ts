// Load static snapshot files for a screen, with loading, error and retry states.
// Files are fetched once per page view and shared between screens; Retry fetches failed ones again.
import { useCallback, useEffect, useState } from 'react'
import type { FileName, Files } from './types'

const cache = new Map<FileName, Promise<unknown>>()

function fetchFile(name: FileName): Promise<unknown> {
  let p = cache.get(name)
  if (!p) {
    p = fetch(`/data/v1/${name}.json`).then(async (r) => {
      if (!r.ok) throw new Error(`${name}.json: HTTP ${r.status}`)
      return r.json()
    })
    p.catch(() => cache.delete(name))
    cache.set(name, p)
  }
  return p
}

export type Loaded<K extends FileName> =
  | { state: 'loading' }
  | { state: 'error'; error: string; retry: () => void }
  | { state: 'ok'; data: Pick<Files, K> }

export function useData<K extends FileName>(names: K[]): Loaded<K> {
  const key = names.join(',')
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<Loaded<K>>({ state: 'loading' })
  const retry = useCallback(() => { setResult({ state: 'loading' }); setAttempt((a) => a + 1) }, [])

  useEffect(() => {
    let live = true
    const list = key.split(',') as K[]
    Promise.all(list.map(fetchFile))
      .then((values) => {
        if (!live) return
        const data = Object.fromEntries(list.map((n, i) => [n, values[i]])) as Pick<Files, K>
        setResult({ state: 'ok', data })
      })
      .catch((e: unknown) => { if (live) setResult({ state: 'error', error: String(e), retry }) })
    return () => { live = false }
  }, [key, attempt, retry])

  return result
}
