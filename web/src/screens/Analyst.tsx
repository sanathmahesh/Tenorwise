// 06 Analyst: ask in plain English; every number in the answer was checked against the engine
// before it was sent. States: idle, loading, answered, cannot answer, blocked, daily limit, error, commentary.
import { HandPalm, Hourglass, Printer, Prohibit, SealCheck } from '@phosphor-icons/react'
import { useCallback, useEffect, useState } from 'react'
import type { AgentResponse, ValueOut } from '../api/types'
import { SUGGESTED, type AnalystState } from './analystState'
import { useData } from '../api/useData'
import { Md, Progress, ScreenTitle, SidePanel } from '../components/ui'
import { fmtDate, fmtSeconds, MINUS } from '../lib/format'
import { linkNumbers } from '../lib/tags'

const UNITS: Record<string, string> = {
  usd: 'US dollars', usd_per_bp: 'US dollars per basis point', pct: 'percent', bp: 'basis points',
  years: 'years', months: 'months', price: 'per 100 of face', number: 'a plain number',
}

export function Analyst({ analyst: a }: { analyst: AnalystState }) {
  const loaded = useData(['methods', 'meta', 'evidence'])
  const [draft, setDraft] = useState('')
  const [openTag, setOpenTag] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (a.status !== 'loading') return
    const id = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(id)
  }, [a.status])

  const close = useCallback(() => setOpenTag(null), [])

  const busy = a.status === 'loading'
  const elapsed = a.startedAt ? Math.max(0, Math.floor((now - a.startedAt) / 1000)) : 0
  const r = a.response
  const meta = loaded.state === 'ok' ? loaded.data.meta : null
  const date = r?.data_date ? fmtDate(r.data_date) : meta ? fmtDate(meta.data_date) : null
  const production = loaded.state === 'ok' ? loaded.data.evidence.models.find((m) => m.id === loaded.data.meta.llm_model) : undefined
  const open: ValueOut | null = openTag && r ? r.values[openTag] ?? null : null

  return (
    <div className="screen reading">
      <ScreenTitle title="Analyst">
        <p className="intro">
          Ask about the portfolio in plain English. The analyst writes the prose; every number is checked against the
          pricing engine before the answer is shown.
        </p>
      </ScreenTitle>

      <section className="no-print">
        <form className="ask-row" onSubmit={(e) => { e.preventDefault(); if (draft.trim()) a.ask(draft.trim()) }}>
          <input className="input" aria-label="Question" placeholder="Ask a question about the portfolio" value={draft}
            maxLength={1000} onChange={(e) => setDraft(e.target.value)} disabled={busy} />
          <button className="btn btn-primary" type="submit" disabled={busy || !draft.trim()}>Ask</button>
          <button className="btn btn-secondary" type="button" disabled={busy} onClick={a.commentary}>Draft portfolio commentary</button>
        </form>
        {a.status === 'idle' && (
          <>
            <h6 style={{ marginTop: 20 }}>Suggested questions</h6>
            <ul className="suggestions" aria-label="Suggested questions">
              {SUGGESTED.map((q) => (
                <li key={q}><button className="link-button" onClick={() => { setDraft(q); a.ask(q) }}>{q}</button></li>
              ))}
            </ul>
          </>
        )}
      </section>

      {a.status !== 'idle' && a.question && (
        <section>
          <h6 style={{ margin: 0 }}>Question</h6>
          <h2 className="section-head" style={{ fontSize: 19 }}>{a.question}</h2>
        </section>
      )}

      {busy && (
        <section aria-live="polite">
          <Progress label="Working" />
          <p style={{ marginTop: 10 }}>Working. Checking every number against the engine. <span className="sub">{elapsed} s</span></p>
          <p className="sub">Nothing appears until every number in the answer has passed verification.</p>
          {production && (
            <p className="sub">
              Measured on the eval machine for <code>{production.id}</code>: typically {fmtSeconds(production.latency_p50_ms)},
              and {fmtSeconds(production.latency_p95_ms)} at the 95th percentile.
            </p>
          )}
        </section>
      )}

      {a.status === 'answered' && r && !a.isCommentary && (
        <section>
          <span className="badge badge-verified"><SealCheck weight="duotone" size={16} />Every number verified</span>
          <div className="answer" style={{ marginTop: 15 }}><Md onValue={setOpenTag}>{linkNumbers(r.answer_md)}</Md></div>
          <Rule text={r.verification_rule} />
          <p className="sub">Select any highlighted number to see where it comes from. {date && `Market data as of ${date}.`}</p>
          <Trace r={r} />
        </section>
      )}

      {a.status === 'answered' && r && a.isCommentary && (
        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
            <span className="badge badge-verified"><SealCheck weight="duotone" size={16} />Every number verified</span>
            <button className="btn btn-secondary no-print" onClick={() => window.print()}><Printer weight="duotone" size={16} />Print</button>
          </div>
          <article className="sheet">
            {r.notice && <div className="draft-banner">{r.notice}</div>}
            <h2 style={{ margin: 0 }}>Portfolio commentary</h2>
            <p className="sub">Stylized model portfolio{date && ` · Market data as of ${date}`}</p>
            {r.sections.map((s) => (
              <div key={s.heading}>
                <h3>{s.heading}</h3>
                <div className="answer"><Md onValue={setOpenTag}>{linkNumbers(s.body_md)}</Md></div>
              </div>
            ))}
          </article>
          <Rule text={r.verification_rule} />
        </section>
      )}

      {a.status === 'cannot_answer' && r && (
        <section>
          <span className="badge badge-neutral"><HandPalm weight="duotone" size={16} />The analyst declined this question</span>
          <div className="answer" style={{ marginTop: 15 }}><Md>{r.answer_md}</Md></div>
        </section>
      )}

      {a.status === 'blocked' && r && (
        <section>
          <span className="badge badge-blocked"><Prohibit weight="duotone" size={16} />Blocked: verification failed</span>
          <p style={{ marginTop: 15 }}>The answer did not pass the number check, so no text is shown. These are the engine's own figures.</p>
          <table className="table" aria-label="Engine figures">
            <thead><tr><th>Engine figure</th><th className="num">Value</th><th>Tool</th></tr></thead>
            <tbody>
              {(r.fallback ?? []).map((f, i) => (
                <tr key={i}><td>{f.label}</td><td className="num">{f.display.replace(/^-/, '−')}</td><td className="mono" style={{ fontSize: 13 }}>{f.tool}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="sub">Engine output, not reviewed prose. {date && `Market data as of ${date}.`}</p>
          <button className="btn btn-secondary" onClick={a.retry}>Ask again</button>
        </section>
      )}

      {a.status === 'limit' && (
        <section>
          <span className="badge badge-neutral"><Hourglass weight="duotone" size={16} />Daily limit reached</span>
          <p style={{ marginTop: 15 }}>{a.detail ?? 'The analyst has reached its daily limit. The rest of Tenorwise works as usual.'}</p>
        </section>
      )}

      {a.status === 'error' && (
        <section role="alert">
          <p className="state-label loss">Something went wrong</p>
          <p>{a.detail ?? 'The analyst could not answer.'}</p>
          <button className="btn btn-secondary" onClick={a.retry}>Try again</button>
        </section>
      )}

      {open && r && (
        <SidePanel title="Where this number comes from" heading="Where this number comes from" onClose={close}>
          <p style={{ marginTop: 15, marginBottom: 0 }}>{open.label}</p>
          <div className="panel-value">{open.display.replace(/^-/, '−')}</div>
          <dl className="facts">
            <dt>Full value</dt><dd className="mono">{fullValue(open.value)}</dd>
            <dt>Unit</dt><dd>{UNITS[open.unit] ?? open.unit}</dd>
            <dt>Engine tool</dt><dd className="mono">{open.tool}</dd>
            <dt>Arguments</dt><dd className="mono">{JSON.stringify(open.args)}</dd>
            <dt>Inputs</dt>
            <dd>
              {open.inputs.length === 0 ? 'None. Read directly from the tool result.' : open.inputs.map((t) => (
                <div key={t}><button className="link-button" onClick={() => setOpenTag(t)}>{r.values[t]?.label ?? t}</button></div>
              ))}
            </dd>
            {date && <><dt>Data date</dt><dd>{date}</dd></>}
          </dl>
          <h4 className="rule-label">Method</h4>
          <Method id={open.method} methods={loaded.state === 'ok' ? loaded.data.methods.methods : null} />
        </SidePanel>
      )}
    </div>
  )
}

/** The engine's value at full precision, with separators and a true minus sign. */
function fullValue(v: number): string {
  const text = Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 10 })
  return v < 0 ? MINUS + text : text
}

function Rule({ text }: { text: string }) {
  return (
    <>
      <p className="rule-label">Verification rule</p>
      <p style={{ fontSize: 14, marginTop: 0 }}>{text}</p>
    </>
  )
}

function Method({ id, methods }: { id: string; methods: Record<string, { plain_english: string; formula: string }> | null }) {
  if (id.startsWith('derive:')) {
    return <p style={{ fontSize: 15 }}>Calculated by the engine's calculator from the inputs above ({id.slice(7).replace('_', ' ')}).<br /><code className="sub">{id}</code></p>
  }
  const m = methods?.[id]
  return (
    <div style={{ fontSize: 15 }}>
      {m ? <p>{m.plain_english}</p> : null}
      {m?.formula && <p className="mono" style={{ fontSize: 12 }}>{m.formula}</p>}
      <code className="sub">{id}</code>
    </div>
  )
}

function Trace({ r }: { r: AgentResponse }) {
  return (
    <details className="trace no-print">
      <summary>Show trace: {r.trace.length} tool calls, {r.usage.llm_calls} model calls</summary>
      <ul>
        {r.trace.map((t, i) => <li key={i}><code>{t.tool}</code> {JSON.stringify(t.args)}</li>)}
      </ul>
      <p className="sub">Model <code>{r.usage.model}</code>{r.usage.served_tier && `, ${r.usage.served_tier} tier`}.</p>
    </details>
  )
}
