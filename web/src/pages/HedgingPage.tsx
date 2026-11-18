import type { Hedges, Scenarios } from '../api/types'
import { useJson } from '../api/useJson'
import { dv01, money, pct } from '../format'
import { Status } from './Status'

export function HedgingPage() {
  const h = useJson<Hedges>('hedges.json')
  const s = useJson<Scenarios>('scenarios.json')
  if (h.state !== 'ok') return <Status loaded={h} />
  if (s.state !== 'ok') return <Status loaded={s} />
  const d = h.data
  const cell = (st: string, sc: string) => d.grid.find((g) => g.strategy_id === st && g.scenario_id === sc)
  return (
    <section>
      <h2>Hedging the AFS book</h2>
      <p>Market data date: {d.data_date}. Pay-fixed swaps, sized once on today's curve, never rebalanced, treated as perfectly effective fair-value hedges. Swap curve = Treasury zero curve + {d.swap_spread_bp} bp (assumption). AFS DV01 {dv01(d.afs_dv01)}. HTM is not hedged: its interest-rate risk cannot be a hedged risk under ASC 815-20-25-43.</p>
      <table>
        <thead><tr><th>Strategy</th><th>Swaps</th><th>DV01 after</th></tr></thead>
        <tbody>
          {d.strategies.map((st) => (
            <tr key={st.id}><td>{st.name}</td><td>{st.swaps.map((w) => `${w.tenor_years}y ${money(w.notional)} @ ${pct(w.fixed_rate, 3)}`).join('; ') || 'none'}</td><td>{dv01(st.dv01_after)}</td></tr>
          ))}
        </tbody>
      </table>
      <h3>AOCI net of hedges / carry given up (12 months)</h3>
      <table>
        <thead><tr><th>Scenario</th>{d.strategies.map((st) => <th key={st.id}>{st.name}</th>)}</tr></thead>
        <tbody>
          {s.data.scenarios.map((sc) => (
            <tr key={sc.id}><td>{sc.name}</td>{d.strategies.map((st) => {
              const c = cell(st.id, sc.id)
              return <td key={st.id}>{c ? `${money(c.aoci_net)} / ${money(c.carry_given_up)}` : ''}</td>
            })}</tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
