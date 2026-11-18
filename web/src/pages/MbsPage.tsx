import type { Mbs } from '../api/types'
import { useJson } from '../api/useJson'
import { bp, num, pct } from '../format'
import { Status } from './Status'

export function MbsPage() {
  const m = useJson<Mbs>('mbs.json')
  if (m.state !== 'ok') return <Status loaded={m} />
  const d = m.data
  const tsy = new Map(d.comparison_treasury.map((r) => [r.shift_bp, r.price]))
  return (
    <section>
      <h2>Agency mortgage bond (STYLIZED)</h2>
      <p>Market data date: {d.data_date}. {d.stylized_note}</p>
      <p>Pool: WAC {pct(d.pool.wac, 3)} (today's mortgage rate), net coupon {pct(d.pool.net_coupon, 3)}, {d.pool.age_months} months old, {d.pool.remaining_months} months left; discount spread {num(d.pool.discount_spread_bp, 1)} bp so it prices at par.
        Mortgage spread {pct(d.mortgage_rate.spread)} on {d.mortgage_rate.date}. Prepayment S-curve (illustrative, not calibrated): CPR {pct(d.prepayment_model.cpr_min, 0)} to {pct(d.prepayment_model.cpr_max, 0)}, k {d.prepayment_model.k}, x0 {d.prepayment_model.x0}.</p>
      <table>
        <thead><tr><th>Shift</th><th>CPR</th><th>Avg life (y)</th><th>Price</th><th>Eff. duration</th><th>Eff. convexity</th><th>Treasury {pct(d.comparison_treasury_bond.coupon)} {num(d.comparison_treasury_bond.maturity_years, 1)}y price</th></tr></thead>
        <tbody>
          {d.profile.map((r) => (
            <tr key={r.shift_bp}><td>{bp(r.shift_bp)}</td><td>{pct(r.cpr, 1)}</td><td>{num(r.avg_life_years)}</td><td>{num(r.price, 3)}</td><td>{num(r.eff_duration)}</td><td>{num(r.eff_convexity, 1)}</td><td>{num(tsy.get(r.shift_bp) ?? NaN, 3)}</td></tr>
          ))}
        </tbody>
      </table>
      <p>{d.mortgage_rate.attribution}</p>
    </section>
  )
}
