import type { GroupRow, KeyRateDV01, Portfolio } from '../api/types'
import { useJson } from '../api/useJson'
import { dv01, money, num, pct } from '../format'
import { Status } from './Status'

const kr = (k: KeyRateDV01) => [k[2], k[5], k[10], k[30]].map((x) => Math.round(x / 1e3)).join(' / ')

function Groups({ title, rows }: { title: string; rows: GroupRow[] }) {
  return (
    <>
      <h3>{title}</h3>
      <table>
        <thead><tr><th></th><th>Amortized cost</th><th>Market value</th><th>Unrealized</th><th>Weight</th><th>Eff. duration</th><th>Convexity</th><th>DV01</th><th>Key-rate DV01 2/5/10/30y ($k/bp)</th></tr></thead>
        <tbody>
          {rows.map((g) => (
            <tr key={g.id}><td>{g.name}</td><td>{money(g.amortized_cost)}</td><td>{money(g.market_value)}</td><td>{money(g.unrealized)}</td><td>{pct(g.weight)}</td><td>{num(g.eff_duration)}</td><td>{num(g.convexity, 1)}</td><td>{dv01(g.dv01)}</td><td>{kr(g.key_rate_dv01)}</td></tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

export function PortfolioPage() {
  const p = useJson<Portfolio>('portfolio.json')
  if (p.state !== 'ok') return <Status loaded={p} />
  const { summary: s, positions } = p.data
  return (
    <section>
      <h2>Model portfolio</h2>
      <p>Market data date: {p.data.data_date}. {p.data.source.text} <a href={p.data.source.url}>Source (PDF)</a></p>
      <p>Agency mortgage bonds are <strong>stylized</strong>. The IG corporates sleeve is a <strong>proxy</strong> for BNY's fixed-rate credit holdings (mainly foreign covered bonds); BNY holds almost no corporate bonds.</p>
      <p>Market value {money(s.market_value)} · amortized cost {money(s.amortized_cost)} · unrealized {money(s.unrealized)} · effective duration {num(s.eff_duration)} · DV01 {dv01(s.dv01)}</p>
      <Groups title="By sector" rows={p.data.by_sector} />
      <Groups title="By accounting class" rows={p.data.by_class} />
      <h3>Positions</h3>
      <table>
        <thead><tr><th>ID</th><th>Name</th><th>Class</th><th>Face</th><th>Coupon</th><th>Maturity (y)</th><th>Book yield</th><th>Price</th><th>Market value</th><th>Unrealized</th><th>Eff. dur.</th><th>Mod. dur. (yield-based)</th><th>Convexity</th><th>DV01</th></tr></thead>
        <tbody>
          {positions.map((x) => (
            <tr key={x.id}>
              <td>{x.id}</td><td>{x.name}{x.stylized ? ' [stylized]' : ''}</td><td>{x.class}</td><td>{money(x.face)}</td><td>{pct(x.coupon)}</td><td>{num(x.maturity_years, 1)}</td><td>{pct(x.book_yield)}</td><td>{num(x.price)}</td><td>{money(x.market_value)}</td><td>{money(x.unrealized)}</td><td>{num(x.eff_duration)}</td><td>{num(x.mod_duration)}</td><td>{num(x.convexity, 1)}</td><td>{dv01(x.dv01)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
