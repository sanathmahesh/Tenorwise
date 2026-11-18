import { useEffect, useState } from 'react'

// Phase 0 placeholder. It proves three things on a deployed preview:
// 1. the build step's JSON is served as a static file,
// 2. the Python function reads the same JSON,
// 3. numpy and scipy run inside the function (and QuantLib is absent).

type Fetched = { ok: true; data: unknown } | { ok: false; error: string } | null

function useJson(url: string): Fetched {
  const [state, setState] = useState<Fetched>(null)
  useEffect(() => {
    fetch(url)
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        setState({ ok: true, data: await r.json() })
      })
      .catch((e: unknown) => setState({ ok: false, error: String(e) }))
  }, [url])
  return state
}

function Block({ title, url }: { title: string; url: string }) {
  const result = useJson(url)
  return (
    <section>
      <h2>{title}</h2>
      <p>
        <code>{url}</code>
      </p>
      <pre>
        {result === null
          ? 'loading…'
          : result.ok
            ? JSON.stringify(result.data, null, 2)
            : `failed: ${result.error}`}
      </pre>
    </section>
  )
}

function DataDate() {
  const meta = useJson('/data/v1/meta.json')
  let text = 'loading…'
  if (meta?.ok) {
    const date = (meta.data as { data_date: string | null }).data_date
    text = date ?? 'none yet (no market data until Phase 1)'
  } else if (meta && !meta.ok) {
    text = `unavailable (${meta.error})`
  }
  return (
    <p>
      <strong>Market data date:</strong> {text}
    </p>
  )
}

export default function App() {
  return (
    <main>
      <h1>Tenorwise</h1>
      <p>Phase 0 skeleton. Placeholder page with no styling.</p>
      <DataDate />
      <Block title="Static file written by the build step" url="/data/v1/meta.json" />
      <Block title="Build-time numpy/scipy check (static)" url="/data/v1/build_check.json" />
      <Block title="Function: health" url="/api/health" />
      <Block title="Function: deploy check" url="/api/deploy-check" />
    </main>
  )
}
