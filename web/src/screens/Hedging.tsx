// 05 Hedging: net change heatmap, loss avoided against carry given up, key rates before and after,
// and the swaps in each hedge. Hedges are sized on hedges.hedged_book (available-for-sale).
import type { Shared } from '../nav'
import type { GridRow, Hedges, StrategyRow } from '../api/types'
import { useData } from '../api/useData'
import { useWidth } from '../lib/useWidth'
import { Assumption, LoadError, Loading, ScreenTitle } from '../components/ui'
import { fmtBp, fmtMoney, fmtMoney2, fmtPct, typo } from '../lib/format'
import { heatTint, linear, paddedExtent } from '../lib/scales'

const KEYS = ['2', '5', '10', '30'] as const

export function Hedging({ shared }: { shared: Shared }) {
  const loaded = useData(['hedges', 'scenarios', 'meta'])
  if (loaded.state === 'loading') return <Loading />
  if (loaded.state === 'error') return <LoadError title="Hedging" error={loaded.error} retry={loaded.retry} />
  const { hedges, scenarios, meta } = loaded.data
  const presets = scenarios.scenarios.filter((s) => s.id !== 'base')
  const scenario = presets.find((s) => s.id === shared.scenarioId) ?? presets[0]
  const strategy = hedges.strategies.find((s) => s.id === shared.strategyId) ?? hedges.strategies[0]
  const cell = (st: string, sc: string) => hedges.grid.find((g) => g.strategy_id === st && g.scenario_id === sc)!
  const largest = Math.max(...hedges.grid.filter((g) => g.scenario_id !== 'base').map((g) => Math.abs(g.net_delta_mv)))
  const rows = hedges.strategies.map((st) => cell(st.id, scenario.id))

  return (
    <div className="screen">
      <ScreenTitle title="Hedging">
        <p className="intro">
          Four strategies against seven scenarios. Each hedge pays a fixed rate on interest-rate swaps against the
          available-for-sale book. It gains when rates rise. Its carry can be a cost or a gain.
        </p>
      </ScreenTitle>

      <div className="flex-wrap">
        <section style={{ flex: '2 1 560px', minWidth: 0 }}>
          <h2 className="section-head">Net change after the hedge</h2>
          <p className="chart-sub">
            Change in the value of {hedges.hedged_book === 'AFS' ? 'available-for-sale' : hedges.hedged_book} securities plus the gain or
            loss on the swaps. Magenta is a loss, cyan a gain; depth shows size.
          </p>
          <div className="scroll-x">
            <table className="heatmap sticky-first" aria-label="Net change after the hedge">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Strategy</th>
                  {presets.map((s) => (
                    <th key={s.id} style={{ textAlign: 'right' }}>
                      <button aria-pressed={s.id === scenario.id} onClick={() => shared.setScenarioId(s.id)}>{typo(s.name)}</button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {hedges.strategies.map((st) => (
                  <tr key={st.id}>
                    <th scope="row" className="row-label">
                      <button aria-pressed={st.id === strategy.id} onClick={() => shared.setStrategyId(st.id)}>{st.name}</button>
                      <span className="carry">carry given up {fmtMoney(cell(st.id, scenario.id).carry_given_up, { signed: true })}</span>
                    </th>
                    {presets.map((s) => {
                      const v = cell(st.id, s.id).net_delta_mv
                      const ink = v < 0 ? 'var(--color-accent-2)' : 'var(--color-accent)'
                      return (
                        <td key={s.id} style={{ background: `color-mix(in srgb, ${ink} ${heatTint(v, largest)}%, transparent)` }}>
                          {fmtMoney(v, { signed: true })}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="caption">
            Carry given up, under each strategy, is for {typo(scenario.name)} over 12 months. A negative figure means the hedge adds carry.
          </p>
        </section>

        <section style={{ flex: '1 1 300px', minWidth: 0 }}>
          <h2 className="section-head">Loss avoided against carry given up</h2>
          <p className="chart-sub">{typo(scenario.name)}</p>
          <Scatter rows={rows} strategies={hedges.strategies} selected={strategy.id} onSelect={shared.setStrategyId} scenarioName={scenario.name} />
        </section>

        <section style={{ flex: '1 1 300px', minWidth: 0 }}>
          <h2 className="section-head">Rate sensitivity before and after</h2>
          <p className="chart-sub">Available-for-sale DV01 by maturity: unhedged in grey, {strategy.name} in ink</p>
          <PairedBars hedges={hedges} strategy={strategy} />
        </section>

        <section style={{ flex: '1 1 300px', minWidth: 0 }}>
          <h2 className="section-head">Hedge composition</h2>
          <p className="chart-sub">{strategy.name}</p>
          {strategy.swaps.length === 0 ? (
            <p>No swaps. The portfolio is left as it is.</p>
          ) : (
            <table className="table" aria-label="Hedge composition">
              <thead><tr><th>Tenor</th><th className="num">Notional</th><th className="num">Fixed rate</th><th className="num">DV01</th></tr></thead>
              <tbody>
                {strategy.swaps.map((w) => (
                  <tr key={w.tenor_years}>
                    <td>{w.tenor_years} years</td>
                    <td className="num">{fmtMoney(w.notional)}</td>
                    <td className="num">{fmtPct(w.fixed_rate)}</td>
                    <td className="num">{fmtMoney2(w.dv01)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="caption">A pay-fixed swap's DV01 is negative: it gains when rates rise.</p>
        </section>
      </div>

      <section>
        <Assumption assumptions={meta.assumptions} id="A-32" prefix={`Swap spread ${fmtBp(hedges.swap_spread_bp)}. `} />
        <Assumption assumptions={meta.assumptions} id="A-34" />
        <Assumption assumptions={meta.assumptions} id="A-35" />
      </section>
    </div>
  )
}

function Scatter({ rows, strategies, selected, onSelect, scenarioName }: {
  rows: GridRow[]; strategies: StrategyRow[]; selected: string; onSelect: (id: string) => void; scenarioName: string
}) {
  const [ref, width] = useWidth(320)
  const H = 220, L = 56, B = 22
  const xs = paddedExtent(rows.map((r) => r.carry_given_up))
  const ys = paddedExtent(rows.map((r) => r.loss_avoided))
  const X = linear(xs, [L, width - 8])
  const Y = linear(ys, [H, 0])
  const name = (id: string) => strategies.find((s) => s.id === id)?.name ?? id
  return (
    <figure className="chart" ref={ref}>
      <svg width={width} height={H + B} role="img" aria-label={`Loss avoided against carry given up, ${scenarioName}`}>
        <rect className="plot" x={L} y={0} width={width - 8 - L} height={H} />
        <line className="zero" x1={X(0)} x2={X(0)} y1={0} y2={H} />
        <line className="zero" x1={L} x2={width - 8} y1={Y(0)} y2={Y(0)} />
        <text x={L - 6} y={10} textAnchor="end">{fmtMoney(ys[1])}</text>
        <text x={L - 6} y={H} textAnchor="end">{fmtMoney(ys[0])}</text>
        <text x={L} y={H + 15}>{fmtMoney(xs[0])}</text>
        <text x={width - 8} y={H + 15} textAnchor="end">{fmtMoney(xs[1])}</text>
        {placeLabels(rows.map((r) => ({ id: r.strategy_id, x: X(r.carry_given_up), y: Y(r.loss_avoided) })), L + 0.55 * (width - 8 - L))
          .map((p) => {
            const on = p.id === selected
            return (
              <g key={p.id} onClick={() => onSelect(p.id)} style={{ cursor: 'pointer' }}>
                <circle cx={p.x} cy={p.y} r={6} fill={on ? 'var(--ink)' : 'var(--color-bg)'} stroke="var(--ink)" strokeWidth={2} />
                <text className="series-label" x={p.flip ? p.x - 10 : p.x + 10} y={p.labelY} textAnchor={p.flip ? 'end' : 'start'}
                  fontWeight={on ? 600 : 400}>{name(p.id)}</text>
              </g>
            )
          })}
      </svg>
      <figcaption className="caption">
        Across: carry given up over 12 months (left of zero, the hedge adds carry). Up: loss avoided, the swaps' gain.
      </figcaption>
    </figure>
  )
}

/** Labels sit beside their points (flipped left past the threshold); a label that would overlap one
 already placed on the same side moves down a line. Positions only; no figure is computed. */
function placeLabels(points: { id: string; x: number; y: number }[], flipAt: number) {
  const placed: { id: string; x: number; y: number; flip: boolean; labelY: number }[] = []
  for (const p of [...points].sort((a, b) => a.y - b.y)) {
    const flip = p.x > flipAt
    let labelY = p.y + 4
    while (placed.some((q) => q.flip === flip && Math.abs(q.x - p.x) < 140 && Math.abs(q.labelY - labelY) < 14)) labelY += 14
    placed.push({ ...p, flip, labelY })
  }
  return placed
}

function PairedBars({ hedges, strategy }: { hedges: Hedges; strategy: StrategyRow }) {
  const before = hedges.strategies.find((s) => s.id === 'unhedged')?.key_rate_dv01_after
  const all = hedges.strategies.flatMap((s) => KEYS.map((k) => s.key_rate_dv01_after[k]))
  const lo = Math.min(0, ...all), hi = Math.max(0, ...all)
  const pos = linear([lo, hi], [0, 100])
  const bar = (v: number, color: string) => (
    <span style={{ left: `${Math.min(pos(0), pos(v))}%`, width: `${Math.abs(pos(v) - pos(0))}%`, background: color }} />
  )
  return (
    <div className="paired">
      {KEYS.map((k) => (
        <div className="paired-row" key={k}>
          <span>{k} years</span>
          <div className="paired-track">
            <div style={{ position: 'absolute', left: `${pos(0)}%`, top: -3, bottom: -3, width: 1, background: 'var(--color-neutral-600)' }} />
            <div className="paired-bar">{before && bar(before[k], 'var(--grey)')}</div>
            <div className="paired-bar">{bar(strategy.key_rate_dv01_after[k], 'var(--ink)')}</div>
          </div>
          <span className="sub num" style={{ margin: 0 }}>{before && fmtMoney2(before[k])} → {fmtMoney2(strategy.key_rate_dv01_after[k])}</span>
        </div>
      ))}
    </div>
  )
}
