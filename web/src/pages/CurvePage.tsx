import type { Curve } from '../api/types'
import { useJson } from '../api/useJson'
import { num, pct, tenor } from '../format'
import { Status } from './Status'

export function CurvePage() {
  const curve = useJson<Curve>('curve.json')
  if (curve.state !== 'ok') return <Status loaded={curve} />
  return (
    <section>
      <h2>US Treasury curve</h2>
      <p>Market data date: {curve.data.data_date}. Par yields from FRED (semiannual bond-equivalent); zero rates continuously compounded, linear between points.</p>
      <table>
        <thead><tr><th>Tenor</th><th>Par yield</th><th>Zero rate</th><th>Discount factor</th></tr></thead>
        <tbody>
          {curve.data.points.map((p) => (
            <tr key={p.tenor_years}><td>{tenor(p.tenor_years)}</td><td>{pct(p.par_yield, 3)}</td><td>{pct(p.zero_rate, 3)}</td><td>{num(p.discount_factor, 6)}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
