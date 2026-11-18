// 08 About: six strategy pages rendered from docs/strategy/*.md at build time, and four reference pages
// (assumptions from meta.json; limitations and the model card from the repository's own files).
import { useData } from '../api/useData'
import { Loading, Md, ScreenTitle } from '../components/ui'
import { fmtDate } from '../lib/format'
import { EFFORT_TIMINGS_CSV, LIMITATIONS_MD, MODEL_CARD_MD, STRATEGY_DOCS } from '../strategy/docs'
import { parseTimings } from '../strategy/effort'

const REFERENCE = [
  { id: 'assumptions', label: 'Assumptions' },
  { id: 'limitations', label: 'Limitations' },
  { id: 'model-card', label: 'Model card' },
  { id: 'data-sources', label: 'Data sources' },
]

export function EffortTimings({ csv }: { csv: string }) {
  const { rows, errors } = parseTimings(csv)
  return (
    <div>
      <h2>Recorded timings</h2>
      {rows.length === 0
        ? <p className="empty-block"><strong>Study not run.</strong> The owner decided not to run it (decision log D-081), so the time Tenorwise saves has not been measured.</p>
        : (
          <>
          <p>Operator: one non-expert (the author, with no finance background). The timings describe this operator only.</p>
          <div className="md-table">
            <table>
              <thead>
                <tr><th>Task</th><th>Method</th><th>Date</th><th>Start</th><th>End</th><th>Minutes</th><th>Completed</th><th>Matches engine</th><th>Notes</th></tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td>{r.task_id}</td><td>{r.method}</td><td>{r.date}</td><td>{r.start_time}</td><td>{r.end_time}</td>
                    <td>{r.minutes}</td><td>{r.completed}</td><td>{r.matches_engine}</td><td>{r.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      {errors.length > 0 && (
        <div role="alert">
          <p>Rows not shown because they are malformed:</p>
          <ul>{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}
    </div>
  )
}

export function About({ docId }: { docId: string | null }) {
  const loaded = useData(['meta', 'portfolio', 'mbs'])
  const id = docId ?? STRATEGY_DOCS[0].id
  const doc = STRATEGY_DOCS.find((d) => d.id === id)
  const link = (pid: string, label: string) => (
    <li key={pid}><a href={`#/about/${pid}`} aria-current={pid === id ? 'page' : undefined}>{label}</a></li>
  )

  return (
    <div className="screen">
      <ScreenTitle title="About">
        <p className="intro">Why Tenorwise exists, how its AI is governed, and what it assumes.</p>
      </ScreenTitle>
      <div className="about">
        <nav className="about-nav" aria-label="About pages">
          <h2>Strategy</h2>
          <ul>{STRATEGY_DOCS.map((d) => link(d.id, d.label))}</ul>
          <h2>Reference</h2>
          <ul>{REFERENCE.map((r) => link(r.id, r.label))}</ul>
        </nav>
        <article className="md">
          {doc ? (
            <>
              <Md>{doc.markdown}</Md>
              {doc.id === 'effort' && <EffortTimings csv={EFFORT_TIMINGS_CSV} />}
            </>
          ) : loaded.state !== 'ok' && id !== 'limitations' ? (
            <Loading />
          ) : (
            <Reference id={id} data={loaded.state === 'ok' ? loaded.data : null} />
          )}
        </article>
      </div>
    </div>
  )
}

type RefData = { meta: import('../api/types').Meta; portfolio: import('../api/types').Portfolio; mbs: import('../api/types').Mbs }

function Reference({ id, data }: { id: string; data: RefData | null }) {
  if (id === 'limitations') {
    return (
      <>
        <Md>{LIMITATIONS_MD}</Md>
        {data && <p className="sub">Market data as of {fmtDate(data.meta.data_date)}.</p>}
      </>
    )
  }
  if (!data) return null
  if (id === 'model-card') {
    return (
      <>
        <p className="sub">Model in production: <code>{data.meta.llm_model ?? 'not configured in this build'}</code></p>
        <Md>{MODEL_CARD_MD}</Md>
      </>
    )
  }
  if (id === 'data-sources') {
    return (
      <>
        <h1>Data sources</h1>
        <h2>Yield curve</h2>
        <p>US Treasury par yields from FRED (Federal Reserve H.15 release), observed {fmtDate(data.meta.data_date)}.</p>
        <ul>{data.meta.fred_series.map((f) => <li key={f.id}><code>{f.id}</code>: {f.title}. {f.use}.</li>)}</ul>
        <h2>Mortgage rate</h2>
        <p>{data.mbs.mortgage_rate.attribution}</p>
        <h2>Portfolio mix</h2>
        <p><a href={data.portfolio.source.url}>{data.portfolio.source.text}</a></p>
      </>
    )
  }
  return (
    <>
      <h1>Assumptions</h1>
      <p>Every simplifying assumption the engine makes, where it is used, and its likely effect.</p>
      <div className="md-table">
        <table>
          <thead><tr><th>ID</th><th>Assumption</th><th>Where</th><th>Effect</th></tr></thead>
          <tbody>
            {data.meta.assumptions.map((a) => (
              <tr key={a.id}><td className="nowrap">{a.id}</td><td>{a.text}</td><td>{a.where}</td><td>{a.effect}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
