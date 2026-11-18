// 04 Scenarios: presets, a custom scenario priced by the engine (POST /api/scenario), and the results.
import { useState } from 'react'
import type { Shared } from '../nav'
import { priceScenario } from '../api/client'
import type { Curve, ScenarioEntry } from '../api/types'
import { useData } from '../api/useData'
import { LineChart } from '../components/charts'
import { Assumption, Figure, LoadError, Loading, Progress, ScreenTitle } from '../components/ui'
import { fmtBp, fmtMoney, fmtPct, tenorLabel, tone, typo } from '../lib/format'
import { halfPointDomain, sqrtMaturity } from '../lib/scales'

const KEYS = ['2', '5', '10', '30'] as const
type Key = (typeof KEYS)[number]

function Slider({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <label style={{ display: 'grid', gridTemplateColumns: '6em 1fr 5em', gap: 10, alignItems: 'center', fontSize: 14 }}>
      <span>{label}</span>
      <input type="range" min={-300} max={300} step={25} value={value} aria-label={label}
        onChange={(e) => onChange(Number(e.target.value))} style={{ accentColor: 'var(--color-accent)', minHeight: 32 }} />
      <span className="num">{fmtBp(value)}</span>
    </label>
  )
}

export function Scenarios({ shared }: { shared: Shared }) {
  const loaded = useData(['scenarios', 'curve', 'meta'])
  const [mode, setMode] = useState<'parallel' | 'key_rate'>('parallel')
  const [parallelBp, setParallelBp] = useState(50)
  const [keyRates, setKeyRates] = useState<Record<Key, number>>({ '2': 0, '5': 0, '10': 50, '30': 0 })
  const [pricing, setPricing] = useState(false)
  const [custom, setCustom] = useState<ScenarioEntry | null>(null)
  const [showCustom, setShowCustom] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (loaded.state === 'loading') return <Loading />
  if (loaded.state === 'error') return <LoadError title="Scenarios" error={loaded.error} retry={loaded.retry} />
  const { scenarios, curve, meta } = loaded.data
  const presets = scenarios.scenarios.filter((s) => s.id !== 'base')
  const base = scenarios.scenarios.find((s) => s.id === 'base')
  const selected = showCustom && custom ? custom : presets.find((s) => s.id === shared.scenarioId) ?? presets[0]

  async function price() {
    setPricing(true); setError(null)
    const req = mode === 'parallel' ? { parallel_bp: parallelBp } : { key_rate_bp: keyRates }
    const r = await priceScenario(req)
    setPricing(false)
    if (r.ok) { setCustom(r.body.scenario); setShowCustom(true) } else setError(r.detail)
  }

  return (
    <div className="screen">
      <ScreenTitle title="Scenarios">
        <p className="intro">
          Choose a move in rates. The unhedged portfolio is repriced on the shifted curve, and the change is split by
          sector and by how the accounts treat it.
        </p>
      </ScreenTitle>

      <section>
        <ul className="strip" aria-label="Preset scenarios">
          {presets.map((s) => (
            <li key={s.id}>
              <button className="cell" aria-pressed={!showCustom && s.id === selected.id}
                onClick={() => { shared.setScenarioId(s.id); setShowCustom(false) }}>
                <span className="cell-name">{typo(s.name)}</span>
                <span className={`cell-sub ${tone(s.total.delta_mv)}`}>{fmtMoney(s.total.delta_mv, { signed: true })}</span>
              </button>
            </li>
          ))}
        </ul>

        <div className="card no-print" style={{ maxWidth: 560, marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span className="card-title" style={{ fontSize: 15 }}>Custom scenario</span>
            <div className="seg" role="radiogroup" aria-label="Shock type">
              {(['parallel', 'key_rate'] as const).map((m) => (
                <label className="seg-opt" key={m}>
                  <input type="radio" name="mode" checked={mode === m} onChange={() => setMode(m)} />
                  {m === 'parallel' ? 'Parallel shift' : 'Key-rate shocks'}
                </label>
              ))}
            </div>
          </div>
          {mode === 'parallel'
            ? <Slider label="All rates" value={parallelBp} onChange={setParallelBp} />
            : KEYS.map((k) => <Slider key={k} label={`${k} years`} value={keyRates[k]} onChange={(v) => setKeyRates({ ...keyRates, [k]: v })} />)}
          <div>
            <button className="btn btn-primary" onClick={price} disabled={pricing} style={{ minHeight: 44 }}>
              {pricing ? 'Pricing' : 'Price scenario'}
            </button>
          </div>
          {error && <p className="loss" role="alert" style={{ fontSize: 14, margin: 0 }}>{error}</p>}
          <p className="card-body">Each shock runs from {fmtBp(-300)} to {fmtBp(300)}. The engine prices it on request.</p>
        </div>
      </section>

      {pricing ? (
        <section aria-busy="true">
          <Progress label="Pricing" />
          <p className="sub">Pricing this scenario on the engine.</p>
          <div className="figures" style={{ marginTop: 20 }}>{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 70 }} />)}</div>
        </section>
      ) : (
        <Results scenario={selected} baseCarry={base?.total.carry_12m} curve={curve} />
      )}

      <section>
        <Assumption assumptions={meta.assumptions} id="A-27" />
        <Assumption assumptions={meta.assumptions} id="A-30" />
      </section>
    </div>
  )
}

function Results({ scenario: s, baseCarry, curve }: { scenario: ScenarioEntry; baseCarry?: number; curve: Curve }) {
  const largest = Math.max(...s.by_sector.map((g) => Math.abs(g.delta_mv))) || 1
  const values = curve.points.map((p) => p.par_yield).concat(s.shocked_curve.map((p) => p.par_yield))
  const notes = s.shock_bp_by_tenor
    .filter((p) => [2, 10, 30].includes(p.tenor_years))
    .map((p) => ({ x: p.tenor_years, y: s.shocked_curve.find((c) => c.tenor_years === p.tenor_years)!.par_yield, text: fmtBp(p.shock_bp) }))
  return (
    <section>
      <h2 className="section-head">{typo(s.name)}</h2>
      <p className="chart-sub">{s.description}</p>
      <div className="figures" style={{ marginTop: 15 }}>
        <Figure label="Change in market value" value={fmtMoney(s.total.delta_mv, { signed: true })} tone={tone(s.total.delta_mv)}
          caption={`${fmtPct(s.total.delta_mv_pct, { signed: true })} of market value`} />
        <Figure label="Impact on AOCI" value={fmtMoney(s.total.aoci_impact, { signed: true })} tone={tone(s.total.aoci_impact)}
          caption="available-for-sale securities" />
        <Figure label="Held-to-maturity change" value={fmtMoney(s.total.htm_unrecognized, { signed: true })}
          caption="not recognized in the accounts" />
        <Figure label="12-month carry" value={fmtMoney(s.total.carry_12m)}
          caption={baseCarry !== undefined ? `${fmtMoney(baseCarry)} on today's curve` : undefined} />
      </div>
      {s.floor_bound && (
        <p className="caption">Shocked yields were held at 0% at {s.floored_tenor_years.map(tenorLabel).join(', ')}.</p>
      )}

      <div className="three-up" style={{ marginTop: 40 }}>
        <div>
          <h3 className="chart-title">Change by sector</h3>
          <p className="chart-sub">Change in market value</p>
          <div className="diverging">
            {s.by_sector.map((g) => {
              const w = (50 * Math.abs(g.delta_mv)) / largest
              return (
                <div className="div-row" key={g.id}>
                  <span>{g.name}</span>
                  <span className="div-track" aria-hidden="true">
                    <span className="div-zero" />
                    <span className="div-fill" style={g.delta_mv < 0
                      ? { right: '50%', width: `${w}%`, background: 'var(--color-accent-2-600)' }
                      : { left: '50%', width: `${w}%`, background: 'var(--color-accent-600)' }} />
                  </span>
                  <span className={`num ${tone(g.delta_mv)}`}>{fmtMoney(g.delta_mv, { signed: true })}</span>
                </div>
              )
            })}
          </div>
        </div>
        <div>
          <h3 className="chart-title">Change by accounting class</h3>
          <p className="chart-sub">Where the change lands in the accounts</p>
          <table className="table" aria-label="Change by accounting class">
            <thead><tr><th /><th className="num">Change</th><th className="num">In AOCI</th><th className="num">Not recognized</th></tr></thead>
            <tbody>
              {s.by_class.map((g) => (
                <tr key={g.id}>
                  <td>{g.name}</td>
                  <td className={`num ${tone(g.delta_mv)}`}>{fmtMoney(g.delta_mv, { signed: true })}</td>
                  <td className="num">{fmtMoney(g.aoci_impact, { signed: true })}</td>
                  <td className="num">{fmtMoney(g.htm_unrecognized, { signed: true })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3 className="chart-title">Curve before and after</h3>
          <p className="chart-sub">Treasury par yield, percent. Before in grey, after in ink.</p>
          <LineChart
            title={`Par curve before and after ${s.name}`}
            height={150}
            x={{ domain: [0, 30], map: (t) => sqrtMaturity(t), ticks: [1, 2, 5, 10, 20, 30].map((t) => ({ value: t, label: String(t) })) }}
            y={{ domain: halfPointDomain(values), format: (v) => fmtPct(v) }}
            series={[
              { points: curve.points.map((p) => [p.tenor_years, p.par_yield]), tone: 'grey' },
              { points: s.shocked_curve.map((p) => [p.tenor_years, p.par_yield]), tone: 'ink' },
            ]}
            notes={notes}
            caption="Maturity in years, square-root scale. Labels show the shock at 2, 10 and 30 years."
          />
        </div>
      </div>
    </section>
  )
}
