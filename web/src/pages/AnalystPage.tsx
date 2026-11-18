import { useState, type ReactNode } from 'react'
import type { components } from '../api/schema'
import { useJson } from '../api/useJson'
import type { Meta } from '../api/types'

type AgentResponse = components['schemas']['AgentResponse']
type ValueOut = components['schemas']['ValueOut']
type MethodsFile = components['schemas']['Methods']
type Turn = { role: 'user' | 'assistant'; content: string }

/** Turn "falls by -$412.3M[[v12]]" into text with the number as a link to its provenance. */
function withLinks(text: string, values: Record<string, ValueOut>, pick: (id: string) => void): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  for (const m of text.matchAll(/\[\[(v\d+)\]\]/g)) {
    const id = m[1]
    const end = m.index ?? 0
    const v = values[id]
    let start = end
    if (v && text.slice(0, end).endsWith(v.display)) start = end - v.display.length
    else while (start > last && !/\s/.test(text[start - 1])) start--
    out.push(text.slice(last, start))
    out.push(
      <a
        key={`${id}-${end}`}
        href="#"
        title={`${id}: ${v?.label ?? 'unknown'}`}
        onClick={(e) => {
          e.preventDefault()
          pick(id)
        }}
      >
        {text.slice(start, end)}
      </a>,
    )
    last = end + m[0].length
  }
  out.push(text.slice(last))
  return out
}

function Provenance(props: { id: string; values: Record<string, ValueOut>; methods: MethodsFile | null; pick: (id: string) => void }) {
  const { id, values, methods, pick } = props
  const v = values[id]
  if (!v) return null
  const method = v.method.startsWith('derive:') ? null : methods?.methods[v.method]
  const args = Object.entries(v.args)
    .map(([k, a]) => `${k}=${JSON.stringify(a)}`)
    .join(', ')
  return (
    <aside>
      <h3>Provenance of {id}</h3>
      <table>
        <tbody>
          <tr><td>Value</td><td>{v.display} ({v.value} {v.unit})</td></tr>
          <tr><td>Label</td><td>{v.label}</td></tr>
          <tr><td>Tool</td><td>{v.tool}({args})</td></tr>
          <tr><td>Method</td><td>{method ? `${method.name}: ${method.plain_english} Formula: ${method.formula}` : v.method}</td></tr>
          {v.inputs.length > 0 && (
            <tr>
              <td>Inputs</td>
              <td>
                {v.inputs.map((i) => (
                  <a
                    key={i}
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      pick(i)
                    }}
                  >
                    {i}{' '}
                  </a>
                ))}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </aside>
  )
}

function Paragraphs({ text, values, pick }: { text: string; values: Record<string, ValueOut>; pick: (id: string) => void }) {
  return (
    <>
      {text.split(/\n\s*\n/).map((para, i) => (
        <p key={i}>{withLinks(para, values, pick)}</p>
      ))}
    </>
  )
}

export function AnalystPage() {
  const meta = useJson<Meta>('meta.json')
  const methodsFile = useJson<MethodsFile>('methods.json')
  const methods = methodsFile.state === 'ok' ? methodsFile.data : null
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<Turn[]>([])
  const [result, setResult] = useState<AgentResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)

  const call = async (path: string, body: object, asked?: string) => {
    setBusy(true)
    setError(null)
    setPicked(null)
    try {
      const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (!r.ok) {
        const detail = ((await r.json().catch(() => ({}))) as { detail?: unknown }).detail
        setResult(null)
        setError(`HTTP ${r.status}: ${typeof detail === 'string' ? detail : 'request rejected'}`)
        return
      }
      const res = (await r.json()) as AgentResponse
      setResult(res)
      if (asked && (res.status === 'answered' || res.status === 'cannot_answer')) {
        const turns: Turn[] = [
          { role: 'user', content: asked },
          { role: 'assistant', content: res.answer_md },
        ]
        setHistory((h) => [...h, ...turns].slice(-10))
      }
    } finally {
      setBusy(false)
    }
  }

  const values = result?.values ?? {}
  return (
    <section>
      <h2>AI analyst</h2>
      <p>
        Market data date: {meta.state === 'ok' ? meta.data.data_date : '…'}. Every number is a link to the calculation behind it.
      </p>
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={3}
        cols={80}
        maxLength={1000}
        placeholder="e.g. What would a repeat of 2022 do to AOCI, and how much would a full DV01 hedge avoid?"
      />
      <div>
        <button disabled={busy || !question.trim()} onClick={() => call('/api/agent/ask', { question, history }, question)}>
          Ask
        </button>{' '}
        <button disabled={busy} onClick={() => call('/api/agent/commentary', {})}>
          Draft commentary
        </button>{' '}
        {busy && 'Working…'}
      </div>
      {error && <p>{error}</p>}
      {result && (
        <div>
          <p>
            <strong>Status: {result.status}</strong>
            {result.notice && <strong> · {result.notice}</strong>}
          </p>
          {result.answer_md && <Paragraphs text={result.answer_md} values={values} pick={setPicked} />}
          {result.sections.map((s) => (
            <div key={s.heading}>
              <h3>{s.heading}</h3>
              <Paragraphs text={s.body_md} values={values} pick={setPicked} />
            </div>
          ))}
          {result.status === 'blocked' && result.fallback && (
            <>
              <p>The answer was blocked because a number could not be verified. Raw engine results instead:</p>
              <table>
                <thead><tr><th>Value</th><th>Label</th><th>Tool</th></tr></thead>
                <tbody>
                  {result.fallback.map((r, i) => (
                    <tr key={i}><td>{r.display}</td><td>{r.label}</td><td>{r.tool}</td></tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          {result.error && <p>Error: {result.error}</p>}
          {picked && <Provenance id={picked} values={values} methods={methods} pick={setPicked} />}
          <p>
            <small>
              {result.checks.filter((c) => c.passed).length}/{result.checks.length} numbers verified. {result.verification_rule}
            </small>
          </p>
          <p>
            <small>
              {result.usage.model} ({result.usage.served_tier ?? 'tier unknown'}), {result.usage.llm_calls} model calls, {result.usage.latency_ms} ms
              {result.usage.cost_usd != null &&
                `, about $${result.usage.cost_usd.toFixed(4)}${result.usage.cost_is_upper_bound ? ' (upper bound)' : ''}`}
            </small>
          </p>
        </div>
      )}
    </section>
  )
}
