import { useState } from 'react'
import type { GridRow, ScenarioEntry, ScenarioResponse, Scenarios } from '../api/types'
import { useJson } from '../api/useJson'
import { money, pct } from '../format'
import { Status } from './Status'

function ScenarioRows({ rows }: { rows: ScenarioEntry[] }) {
  return (
    <table>
      <thead><tr><th>Scenario</th><th>Change in value</th><th>%</th><th>AOCI impact (AFS)</th><th>HTM, not recognized</th><th>12-month carry</th><th>Floor</th></tr></thead>
      <tbody>
        {rows.map((s) => (
          <tr key={s.id} title={s.description}><td>{s.name}</td><td>{money(s.total.delta_mv)}</td><td>{pct(s.total.delta_mv_pct)}</td><td>{money(s.total.aoci_impact)}</td><td>{money(s.total.htm_unrecognized)}</td><td>{money(s.total.carry_12m)}</td><td>{s.floor_bound ? 'binds' : ''}</td></tr>
        ))}
      </tbody>
    </table>
  )
}

function GridRows({ rows }: { rows: GridRow[] }) {
  return (
    <table>
      <thead><tr><th>Strategy</th><th>AOCI net of hedges</th><th>Loss avoided</th><th>Carry given up</th><th>Net carry</th></tr></thead>
      <tbody>
        {rows.map((g) => (
          <tr key={g.strategy_id}><td>{g.strategy_id}</td><td>{money(g.aoci_net)}</td><td>{money(g.loss_avoided)}</td><td>{money(g.carry_given_up)}</td><td>{money(g.net_carry)}</td></tr>
        ))}
      </tbody>
    </table>
  )
}

function CustomScenario() {
  const [shift, setShift] = useState('100')
  const [result, setResult] = useState<ScenarioResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const run = async () => {
    setError(null)
    const r = await fetch('/api/scenario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parallel_bp: Number(shift) }),
    })
    if (!r.ok) {
      setResult(null)
      setError(r.status === 422 ? 'Shift must be a number from -300 to +300 bp.' : `HTTP ${r.status}`)
      return
    }
    setResult((await r.json()) as ScenarioResponse)
  }
  return (
    <>
      <h3>Custom parallel shift</h3>
      <label>Shift (bp, -300 to +300): <input value={shift} onChange={(e) => setShift(e.target.value)} size={6} /></label>{' '}
      <button onClick={run}>Run</button>
      {error && <p>{error}</p>}
      {result && (
        <>
          <p>Market data date: {result.data_date}.</p>
          <ScenarioRows rows={[result.scenario]} />
          <GridRows rows={result.grid} />
        </>
      )}
    </>
  )
}

export function ScenariosPage() {
  const s = useJson<Scenarios>('scenarios.json')
  if (s.state !== 'ok') return <Status loaded={s} />
  return (
    <section>
      <h2>Scenarios</h2>
      <p>Market data date: {s.data.data_date}. Instantaneous shocks to Treasury par yields; spreads held fixed; amounts pre-tax. Base market value {money(s.data.base_market_value)}.</p>
      <ScenarioRows rows={s.data.scenarios} />
      <CustomScenario />
    </section>
  )
}
