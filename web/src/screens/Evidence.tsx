// 07 Evidence: only the fields in evidence.json; nothing derived.
import { useData } from '../api/useData'
import { Empty, LoadError, Loading, ScreenTitle } from '../components/ui'
import { fmtCost, fmtDate, fmtFraction, fmtSci, fmtSeconds } from '../lib/format'

const CATEGORY: Record<string, string> = {
  lookup: 'Lookup', scenario: 'Scenario', hedge: 'Hedge', derived: 'Derived figure', mortgage: 'Mortgage', decline: 'Should decline',
}

export function Evidence() {
  const loaded = useData(['evidence', 'meta'])
  if (loaded.state === 'loading') return <Loading />
  if (loaded.state === 'error') return <LoadError title="Evidence" error={loaded.error} retry={loaded.retry} />
  const { evidence, meta } = loaded.data

  return (
    <div className="screen">
      <ScreenTitle title="Evidence">
        <p className="intro">
          How the analyst and the pricing code were tested. Each language model answered the same questions, and the
          pricing code was compared with QuantLib, an open-source pricing library.
        </p>
        <p className="sub">
          Data as of {fmtDate(evidence.data_date)} · QuantLib report generated {fmtDate(evidence.quantlib_report_generated_at)}
        </p>
      </ScreenTitle>

      <section>
        <h2 className="section-head">Analyst eval by model</h2>
        <p className="chart-sub" style={{ maxWidth: '40em' }}>
          Accuracy is the share of questions answered correctly. Blocked is the share withheld after one repair attempt.
          Verified but wrong is the share that passed verification and was still incorrect. Times are measured on the eval machine.
        </p>
        {evidence.models.length === 0 ? (
          <Empty>No eval results are published in this build.</Empty>
        ) : (
          <div className="model-blocks" style={{ marginTop: 20 }}>
            {evidence.models.map((m) => (
              <section key={m.id} aria-label={m.id}>
                <h3>{m.id}</h3>
                {m.id === meta.llm_model && <span className="sub">In production</span>}
                <div className="figure-value" style={{ marginTop: 10 }}>{fmtFraction(m.accuracy)}</div>
                <div className="figure-caption" style={{ marginTop: 0 }}>accuracy</div>
                <dl>
                  <dt>Answers blocked</dt><dd>{fmtFraction(m.block_rate)}</dd>
                  <dt>Verified but wrong</dt><dd>{fmtFraction(m.verified_but_wrong_rate)}</dd>
                  <dt>Median time</dt><dd>{fmtSeconds(m.latency_p50_ms)}</dd>
                  <dt>95th percentile time</dt><dd>{fmtSeconds(m.latency_p95_ms)}</dd>
                  <dt>Cost per question</dt><dd>{fmtCost(m.cost_per_question_usd)}</dd>
                  <dt>Runs</dt><dd>{m.runs}</dd>
                </dl>
              </section>
            ))}
          </div>
        )}
      </section>

      {evidence.questions.length > 0 && (
        <section>
          <h2 className="section-head">Results by question</h2>
          <p className="chart-sub">The outcome in most of the repeats, per model.</p>
          <div className="scroll-x">
            <table className="table" aria-label="Results by question" style={{ minWidth: 680 }}>
              <thead>
                <tr>
                  <th>Category</th><th>Question</th>
                  {evidence.models.map((m) => <th key={m.id} className="mono" style={{ textTransform: 'none' }}>{m.id.split('/').pop()}</th>)}
                </tr>
              </thead>
              <tbody>
                {evidence.questions.map((q) => (
                  <tr key={q.id}>
                    <td className="nowrap">{CATEGORY[q.category] ?? q.category}</td>
                    <td>{q.text}</td>
                    {evidence.models.map((m) => {
                      const r = q.results[m.id]
                      return <td key={m.id} className={r === 'fail' ? 'result-fail' : r === 'blocked' ? 'result-blocked' : undefined}>
                        {r ? r[0].toUpperCase() + r.slice(1) : ''}
                      </td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <h2 className="section-head">Agreement with QuantLib</h2>
        <p className="chart-sub">Largest difference between this tool's pricing code and the benchmark, per measure</p>
        <div className="scroll-x">
          <table className="table" aria-label="Agreement with QuantLib">
            <thead><tr><th>Measure</th><th className="num">Instruments</th><th className="num">Largest difference</th><th>Unit</th></tr></thead>
            <tbody>
              {evidence.quantlib.map((q) => (
                <tr key={q.measure}>
                  <td>{q.measure.replace(/_/g, ' ')}</td>
                  <td className="num">{q.instruments}</td>
                  <td className="num">{fmtSci(q.max_abs_diff)}</td>
                  <td>{q.unit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
