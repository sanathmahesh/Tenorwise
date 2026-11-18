// 01 Overview: the position at a glance and the way into the other screens.
import { useState } from 'react'
import type { Shared } from '../nav'
import { useData } from '../api/useData'
import { Figure, LoadError, Loading, ScreenTitle } from '../components/ui'
import { fmtMoney, fmtNum, fmtPct, tone, typo } from '../lib/format'

const KEY_RATES = ['2', '5', '10', '30'] as const

export function Overview({ shared, onAsk }: { shared: Shared; onAsk: (q: string) => void }) {
  const loaded = useData(['portfolio', 'scenarios'])
  const [question, setQuestion] = useState('')
  if (loaded.state === 'loading') return <Loading />
  if (loaded.state === 'error') return <LoadError title="Overview" error={loaded.error} retry={loaded.retry} />
  const { portfolio, scenarios } = loaded.data
  const s = portfolio.summary
  const largestSector = Math.max(...portfolio.by_sector.map((g) => g.market_value))
  const afs = portfolio.by_class.find((g) => g.id === 'AFS')
  const htm = portfolio.by_class.find((g) => g.id === 'HTM')
  const largestKr = Math.max(...KEY_RATES.map((k) => Math.abs(s.key_rate_dv01[k])))
  const presets = scenarios.scenarios.filter((x) => x.id !== 'base')

  return (
    <div className="screen">
      <ScreenTitle title="Overview">
        <p className="intro">
          A model bond portfolio whose sector mix follows BNY's Form 10-Q. If interest rates move, this is how much it
          loses and which hedge is worth its cost.
        </p>
      </ScreenTitle>

      <section className="figures" aria-label="Portfolio summary">
        <Figure label="Market value" value={fmtMoney(s.market_value)} />
        <Figure label="Amortized cost" value={fmtMoney(s.amortized_cost)} />
        <Figure
          label={s.unrealized < 0 ? 'Unrealized loss' : 'Unrealized gain'}
          value={fmtMoney(s.unrealized)}
          tone={tone(s.unrealized)}
          caption={afs && htm && `${fmtMoney(afs.unrealized)} available-for-sale, ${fmtMoney(htm.unrealized)} held-to-maturity`}
        />
        <Figure label="Effective duration" value={fmtNum(s.eff_duration)} unit="years" />
        <Figure label="DV01" value={fmtMoney(s.dv01)} caption="lost per 0.01% rise in rates" />
      </section>

      <div className="two-col">
        <section aria-labelledby="mix-head">
          <h2 className="section-head" id="mix-head">Sector mix by accounting class</h2>
          <div className="legend">
            <span><span className="swatch" style={{ background: 'var(--ink)' }} />Available-for-sale {afs && fmtPct(afs.weight, { decimals: 1 })}</span>
            <span><span className="swatch" style={{ background: 'var(--grey)' }} />Held-to-maturity {htm && fmtPct(htm.weight, { decimals: 1 })}</span>
          </div>
          <div className="hbars">
            {portfolio.by_sector.map((g) => (
              <div className="hbar-row" key={g.id}>
                <span>{g.name}</span>
                <span className="hbar-track" aria-hidden="true">
                  <span className="hbar-seg" style={{ width: `${(100 * g.market_value_by_class.AFS) / largestSector}%`, background: 'var(--ink)' }} />
                  <span className="hbar-seg" style={{ width: `${(100 * g.market_value_by_class.HTM) / largestSector}%`, background: 'var(--grey)' }} />
                </span>
                <span className="num hbar-figure">{fmtMoney(g.market_value)}</span>
                <span className="hbar-weight">{fmtPct(g.weight, { decimals: 1 })}</span>
              </div>
            ))}
          </div>
          <p className="caption">Bar length is market value; the dark part is available-for-sale. Weights are shares of amortized cost.</p>
        </section>

        <section aria-labelledby="kr-head">
          <h2 className="section-head" id="kr-head">Rate sensitivity by maturity</h2>
          <p className="chart-sub">Value lost per 0.01% rise in the rate at each point on the curve</p>
          <div className="vbars">
            {KEY_RATES.map((k) => (
              <div className="vbar" key={k}>
                <span className="vbar-value">{fmtMoney(s.key_rate_dv01[k])}</span>
                <span className="vbar-fill" style={{ height: `${(100 * Math.max(0, s.key_rate_dv01[k])) / largestKr * 0.8}%` }} />
                <span className="vbar-label">{k} years</span>
              </div>
            ))}
          </div>
          <p className="caption">Key-rate DV01: the dollars lost when only that point of the curve rises 0.01%.</p>
        </section>
      </div>

      <section aria-labelledby="sc-head">
        <h2 className="section-head" id="sc-head">Seven scenarios</h2>
        <p className="chart-sub">Change in the portfolio's market value. Select one to see the hedges.</p>
        <ul className="strip" aria-label="Scenarios">
          {presets.map((x) => (
            <li key={x.id}>
              <button
                className="cell"
                aria-pressed={x.id === shared.scenarioId}
                onClick={() => { shared.setScenarioId(x.id); shared.go('Hedging') }}
              >
                <span className="cell-name">{typo(x.name)}</span>
                <span className={`cell-value ${tone(x.total.delta_mv)}`}>{fmtMoney(x.total.delta_mv, { signed: true })}</span>
                <span className="cell-sub">{fmtPct(x.total.delta_mv_pct, { signed: true })}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="ask-head" className="reading">
        <h2 className="section-head" id="ask-head">Ask the analyst</h2>
        <form className="ask-row" onSubmit={(e) => { e.preventDefault(); if (question.trim()) onAsk(question.trim()) }}>
          <input
            className="input" aria-label="Ask the analyst" placeholder="Ask a question about the portfolio"
            value={question} maxLength={1000} onChange={(e) => setQuestion(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={!question.trim()}>Ask</button>
        </form>
      </section>
    </div>
  )
}
