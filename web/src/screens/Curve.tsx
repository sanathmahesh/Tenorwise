// 02 Curve: par and zero curves, with a scenario overlay.
import { useState } from 'react'
import type { Shared } from '../nav'
import { useData } from '../api/useData'
import { LineChart, type Series } from '../components/charts'
import { LoadError, Loading, ScreenTitle } from '../components/ui'
import { fmtDate, fmtPct, tenorLabel, typo } from '../lib/format'
import { halfPointDomain, sqrtMaturity } from '../lib/scales'

const TICKS = [1, 2, 5, 10, 20, 30]

export function Curve({ shared }: { shared: Shared }) {
  const loaded = useData(['curve', 'scenarios', 'meta'])
  const [overlay, setOverlay] = useState<string | null>(shared.scenarioId === 'base' ? null : shared.scenarioId)
  if (loaded.state === 'loading') return <Loading />
  if (loaded.state === 'error') return <LoadError title="Curve" error={loaded.error} retry={loaded.retry} />
  const { curve, scenarios, meta } = loaded.data
  const presets = scenarios.scenarios.filter((s) => s.id !== 'base')
  const chosen = presets.find((s) => s.id === overlay) ?? null
  const values = curve.points.flatMap((p) => [p.par_yield, p.zero_rate]).concat(chosen ? chosen.shocked_curve.map((p) => p.par_yield) : [])
  const series: Series[] = [
    { points: curve.points.map((p) => [p.tenor_years, p.par_yield]), tone: 'ink', label: 'Par yield' },
    { points: curve.points.map((p) => [p.tenor_years, p.zero_rate]), tone: 'grey' },
  ]
  if (chosen) {
    series.push({ points: chosen.shocked_curve.map((p) => [p.tenor_years, p.par_yield]), tone: 'ink', dashed: true, label: `Par after ${typo(chosen.name)}` })
  }

  return (
    <div className="screen">
      <ScreenTitle title="Curve">
        <p className="intro">
          US Treasury par yields on the market data date, and the zero curve bootstrapped from them. Every price in
          Tenorwise discounts on this curve.
        </p>
      </ScreenTitle>

      <div className="flex-wrap">
        <section className="grow-2" aria-labelledby="curve-head">
          <h2 className="section-head" id="curve-head">Par and zero curves</h2>
          <p className="chart-sub">Percent, by maturity. Zero rate in grey.</p>
          <LineChart
            title="Par and zero curves"
            height={240}
            x={{ domain: [0, 30], map: (t) => sqrtMaturity(t), ticks: TICKS.map((t) => ({ value: t, label: String(t) })) }}
            y={{ domain: halfPointDomain(values), format: (v) => fmtPct(v) }}
            series={series}
            caption="Maturity in years on a square-root scale. Par yield in ink, zero rate in grey."
          />
          <h3 className="chart-title" style={{ marginTop: 20 }}>Overlay a scenario</h3>
          <div className="pick-row" role="group" aria-label="Overlay a scenario">
            <button className="btn btn-secondary" aria-pressed={!chosen} onClick={() => setOverlay(null)}>None</button>
            {presets.map((s) => (
              <button key={s.id} className="btn btn-secondary" aria-pressed={s.id === overlay} onClick={() => { setOverlay(s.id); shared.setScenarioId(s.id) }}>
                {typo(s.name)}
              </button>
            ))}
          </div>
        </section>

        <section className="grow-1">
          <table className="table">
            <caption className="section-head" style={{ textAlign: 'left' }}>The 11 maturities</caption>
            <thead>
              <tr><th>Maturity</th><th className="num">Par yield</th><th className="num">Zero rate</th><th className="num">After shock</th></tr>
            </thead>
            <tbody>
              {curve.points.map((p, i) => (
                <tr key={p.tenor_years}>
                  <td>{tenorLabel(p.tenor_years)}</td>
                  <td className="num">{fmtPct(p.par_yield)}</td>
                  <td className="num">{fmtPct(p.zero_rate)}</td>
                  <td className="num">{chosen ? fmtPct(chosen.shocked_curve[i].par_yield) : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {chosen && <p className="caption">After shock: par yields under {typo(chosen.name)}.</p>}
        </section>
      </div>

      <section>
        <p className="caption">
          Source: FRED, observed {fmtDate(meta.data_date)}.{' '}
          {meta.fred_series.map((f) => f.id).join(', ')}.
        </p>
      </section>
    </div>
  )
}
