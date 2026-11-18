// 03 Portfolio: sector and class table, sortable positions with a drawer, and the stylized mortgage pool.
import { useCallback, useState } from 'react'
import type { GroupRow, PositionRow } from '../api/types'
import { useData } from '../api/useData'
import { LineChart } from '../components/charts'
import { Assumption, LoadError, Loading, ScreenTitle, SidePanel, Stylized } from '../components/ui'
import { fmtMoney, fmtMoney2, fmtNum, fmtPct, fmtYears, tone } from '../lib/format'

type SortKey = 'name' | 'sector' | 'class' | 'market_value' | 'unrealized' | 'eff_duration' | 'dv01'
const COLUMNS: { key: SortKey; label: string; num: boolean }[] = [
  { key: 'name', label: 'Position', num: false },
  { key: 'sector', label: 'Sector', num: false },
  { key: 'class', label: 'Class', num: false },
  { key: 'market_value', label: 'Market value', num: true },
  { key: 'unrealized', label: 'Unrealized', num: true },
  { key: 'eff_duration', label: 'Duration', num: true },
  { key: 'dv01', label: 'DV01', num: true },
]

function GroupRows({ rows, first }: { rows: GroupRow[]; first?: boolean }) {
  return (
    <>
      {rows.map((g, i) => (
        <tr key={g.id} className={i === 0 && !first ? 'gap' : undefined}>
          <td>{g.name}</td>
          <td className="num">{fmtMoney(g.market_value)}</td>
          <td className="num">{fmtPct(g.weight, { decimals: 1 })}</td>
          <td className={`num ${tone(g.unrealized)}`}>{fmtMoney(g.unrealized)}</td>
          <td className="num">{fmtNum(g.eff_duration)}</td>
          <td className="num">{fmtMoney2(g.dv01)}</td>
        </tr>
      ))}
    </>
  )
}

export function Portfolio() {
  const loaded = useData(['portfolio', 'mbs', 'meta'])
  const [sortKey, setSortKey] = useState<SortKey>('market_value')
  const [sortDir, setSortDir] = useState<1 | -1>(-1)
  const [openId, setOpenId] = useState<string | null>(null)
  const close = useCallback(() => setOpenId(null), [])
  if (loaded.state === 'loading') return <Loading />
  if (loaded.state === 'error') return <LoadError title="Portfolio" error={loaded.error} retry={loaded.retry} />
  const { portfolio, mbs, meta } = loaded.data
  const sectorName = Object.fromEntries(portfolio.by_sector.map((g) => [g.id, g.name]))
  const keyOf = (p: PositionRow, k: SortKey): string | number =>
    k === 'sector' ? sectorName[p.sector] : k === 'class' ? p.class : p[k]
  const rows = [...portfolio.positions].sort((a, b) => {
    const x = keyOf(a, sortKey); const y = keyOf(b, sortKey)
    return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))) * sortDir
  })
  const sortBy = (k: SortKey, num: boolean) => {
    if (k === sortKey) setSortDir((d) => (d === 1 ? -1 : 1))
    else { setSortKey(k); setSortDir(num ? -1 : 1) }
  }
  const open = portfolio.positions.find((p) => p.id === openId) ?? null
  const base = mbs.profile.find((r) => r.shift_bp === 0)
  const tsy = Object.fromEntries(mbs.comparison_treasury.map((r) => [r.shift_bp, r.price]))
  const prices = mbs.profile.flatMap((r) => [r.price, tsy[r.shift_bp]])
  const priceDomain: [number, number] = [Math.floor(Math.min(...prices) / 5) * 5, Math.ceil(Math.max(...prices) / 5) * 5]
  const shiftTicks = [-300, 0, 300].map((v) => ({ value: v, label: v === 0 ? '0' : `${v > 0 ? '+' : '−'}${Math.abs(v)} bp` }))
  const inc = mbs.s_curve.map((r) => r.incentive_pct)
  const cprMax = Math.ceil(Math.max(...mbs.s_curve.map((r) => r.cpr)) / 5) * 5
  const life = mbs.profile.map((r) => r.avg_life_years)

  return (
    <div className="screen">
      <ScreenTitle title="Portfolio">
        <p className="intro">
          Each position stands for a bucket of similar bonds. The agency mortgage pools are stylized, and the IG
          corporates are a proxy for other lines in the filing.
        </p>
        <p className="sub"><a href={portfolio.source.url}>{portfolio.source.text}</a></p>
      </ScreenTitle>

      <section>
        <h2 className="section-head">By sector and accounting class</h2>
        <div className="scroll-x">
          <table className="table">
            <thead>
              <tr><th>Name</th><th className="num">Market value</th><th className="num">Weight</th><th className="num">Unrealized</th><th className="num">Duration</th><th className="num">DV01</th></tr>
            </thead>
            <tbody>
              <GroupRows rows={portfolio.by_sector} first />
              <GroupRows rows={portfolio.by_class} />
              <tr className="total gap">
                <td>Total</td>
                <td className="num">{fmtMoney(portfolio.summary.market_value)}</td>
                <td />
                <td className={`num ${tone(portfolio.summary.unrealized)}`}>{fmtMoney(portfolio.summary.unrealized)}</td>
                <td className="num">{fmtNum(portfolio.summary.eff_duration)}</td>
                <td className="num">{fmtMoney2(portfolio.summary.dv01)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="caption">Duration in years. Weight is the share of amortized cost. DV01 is the value lost per 0.01% rise in rates.</p>
      </section>

      <section>
        <h2 className="section-head">Positions</h2>
        <p className="chart-sub">Select a column heading to sort. Select a position for its details. AFS is available-for-sale, HTM is held-to-maturity.</p>
        <div className="scroll-x">
          <table className="table positions sticky-first" aria-label="Positions">
            <thead>
              <tr>
                {COLUMNS.map((c) => (
                  <th key={c.key} className={c.num ? 'num' : undefined} aria-sort={c.key === sortKey ? (sortDir === 1 ? 'ascending' : 'descending') : undefined}>
                    <button className="sort-button" data-active={c.key === sortKey} onClick={() => sortBy(c.key, c.num)}>
                      {c.label}{c.key === sortKey ? (sortDir === 1 ? ' ↑' : ' ↓') : ''}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id}>
                  <td>
                    <button className="link-button" onClick={() => setOpenId(p.id)}>{p.name}</button>
                    {p.stylized && <> <Stylized /></>}
                  </td>
                  <td>{sectorName[p.sector]}</td>
                  <td>{p.class}</td>
                  <td className="num">{fmtMoney(p.market_value)}</td>
                  <td className={`num ${tone(p.unrealized)}`}>{fmtMoney(p.unrealized)}</td>
                  <td className="num">{fmtNum(p.eff_duration)}</td>
                  <td className="num">{fmtMoney2(p.dv01)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="mbs-head">
        <h2 id="mbs-head" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>Mortgages <Stylized /></h2>
        <p className="intro">
          Homeowners refinance when rates fall. A mortgage bond therefore gains less than a Treasury in a rally and
          loses more in a sell-off. Shown for one stylized agency mortgage pool.
        </p>
        <p className="sub">{mbs.stylized_note}</p>
        <div className="three-up" style={{ marginTop: 30 }}>
          <div>
            <h3 className="chart-title">Price against rate shift <Stylized /></h3>
            <p className="chart-sub">Price per 100 of face: the pool in ink, a Treasury ({fmtPct(mbs.comparison_treasury_bond.coupon)} coupon, {fmtYears(mbs.comparison_treasury_bond.maturity_years)}) in grey.</p>
            <LineChart
              title="Price against rate shift, stylized mortgage pool and Treasury"
              height={180}
              x={{ domain: [-300, 300], ticks: shiftTicks }}
              y={{ domain: priceDomain, format: (v) => fmtNum(v, 0) }}
              series={[
                { points: mbs.comparison_treasury.map((r) => [r.shift_bp, r.price]), tone: 'grey' },
                { points: mbs.profile.map((r) => [r.shift_bp, r.price]), tone: 'ink' },
              ]}
              zeroX
              caption="Parallel shift in rates."
            />
          </div>
          <div>
            <h3 className="chart-title">Prepayment speed <Stylized /></h3>
            <p className="chart-sub">Share of the pool repaid early, percent a year</p>
            <LineChart
              title="Prepayment speed against refinancing incentive, stylized"
              height={180}
              x={{ domain: [Math.min(...inc), Math.max(...inc)], ticks: [Math.min(...inc), 0, Math.max(...inc)].map((v) => ({ value: v, label: fmtPct(v, { decimals: 0, signed: v !== 0 }) })) }}
              y={{ domain: [0, cprMax], format: (v) => fmtPct(v, { decimals: 0 }) }}
              series={[{ points: mbs.s_curve.map((r) => [r.incentive_pct, r.cpr]), tone: 'ink' }]}
              markers={base ? [{ x: base.incentive_pct, y: base.cpr, label: `Today: ${fmtPct(base.cpr, { decimals: 1 })} a year` }] : []}
              caption="Refinancing incentive: the pool's loan rate minus today's mortgage rate, in percentage points."
            />
          </div>
          <div>
            <h3 className="chart-title">Average life <Stylized /></h3>
            <p className="chart-sub">Years until the average dollar of principal is repaid</p>
            <LineChart
              title="Average life against rate shift, stylized"
              height={180}
              x={{ domain: [-300, 300], ticks: shiftTicks }}
              y={{ domain: [Math.floor(Math.min(...life)), Math.ceil(Math.max(...life))], format: (v) => fmtNum(v, 0) }}
              series={[{ points: mbs.profile.map((r) => [r.shift_bp, r.avg_life_years]), tone: 'ink' }]}
              markers={base ? [{ x: 0, y: base.avg_life_years, label: `Today: ${fmtYears(base.avg_life_years)}` }] : []}
              caption="Parallel shift in rates."
            />
          </div>
        </div>
        <div style={{ marginTop: 30 }}>
          <Assumption assumptions={meta.assumptions} id="A-15" />
          <p className="caption">{mbs.mortgage_rate.attribution}</p>
        </div>
      </section>

      {open && (
        <SidePanel title={open.name} heading="Position" onClose={close}>
          <h3 style={{ fontSize: 20, marginTop: 15 }}>{open.name} {open.stylized && <Stylized />}</h3>
          <p className="sub">{sectorName[open.sector]} · {open.class === 'AFS' ? 'Available-for-sale' : 'Held-to-maturity'}</p>
          <div className="panel-value">{fmtMoney(open.market_value)}</div>
          <dl className="facts">
            <dt>Face</dt><dd>{fmtMoney(open.face)}</dd>
            <dt>Price</dt><dd>{fmtNum(open.price)} per 100</dd>
            <dt>Amortized cost</dt><dd>{fmtMoney(open.amortized_cost)}</dd>
            <dt>Unrealized</dt><dd className={tone(open.unrealized)}>{fmtMoney(open.unrealized)}</dd>
            <dt>Coupon</dt><dd>{fmtPct(open.coupon)}{open.stylized ? ' (net)' : ''}</dd>
            <dt>Maturity</dt><dd>{fmtYears(open.maturity_years)}</dd>
            <dt>Stands in for</dt><dd>{open.proxy_for ?? 'Not a proxy'}</dd>
            <dt>Effective duration</dt><dd>{fmtYears(open.eff_duration)}</dd>
            <dt>DV01</dt><dd>{fmtMoney2(open.dv01)}</dd>
          </dl>
          <h4 className="rule-label">Rate sensitivity by maturity</h4>
          <KeyRateBars values={open.key_rate_dv01} />
        </SidePanel>
      )}
    </div>
  )
}

function KeyRateBars({ values }: { values: Record<'2' | '5' | '10' | '30', number> }) {
  const keys = ['2', '5', '10', '30'] as const
  const largest = Math.max(...keys.map((k) => Math.abs(values[k]))) || 1
  return (
    <div className="hbars">
      {keys.map((k) => (
        <div className="hbar-row" key={k} style={{ gridTemplateColumns: '4em 1fr auto' }}>
          <span>{k} years</span>
          <span className="hbar-track"><span className="hbar-seg" style={{ width: `${(100 * Math.max(0, values[k])) / largest}%`, background: 'var(--ink)' }} /></span>
          <span className="num">{fmtMoney2(values[k])}</span>
        </div>
      ))}
    </div>
  )
}
