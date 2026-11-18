// Tenorwise: the implemented design (Phase 11). Eight screens, switched without a page load.
// Every figure on screen comes from the snapshot files or the API; the front end only formats.
import { CalendarBlank } from '@phosphor-icons/react'
import { useCallback, useEffect, useState } from 'react'
import { useData } from './api/useData'
import { SCREENS, type Screen, type Shared } from './nav'
import { fmtDate } from './lib/format'
import { About } from './screens/About'
import { Analyst } from './screens/Analyst'
import { useAnalyst } from './screens/analystState'
import { Curve } from './screens/Curve'
import { Evidence } from './screens/Evidence'
import { Hedging } from './screens/Hedging'
import { Overview } from './screens/Overview'
import { Portfolio } from './screens/Portfolio'
import { Scenarios } from './screens/Scenarios'


function readHash(): { screen: Screen; sub: string | null } {
  const [first, sub] = window.location.hash.replace(/^#\/?/, '').split('/')
  const screen = SCREENS.find((s) => s.toLowerCase() === (first || '').toLowerCase()) ?? 'Overview'
  return { screen, sub: sub ?? null }
}

export default function App() {
  const [route, setRoute] = useState(readHash)
  const [scenarioId, setScenarioId] = useState('parallel_up_100')
  const [strategyId, setStrategyId] = useState('dv01_full')
  const analyst = useAnalyst()

  useEffect(() => {
    const onHash = () => setRoute(readHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => { window.scrollTo?.(0, 0) }, [route.screen])

  const go = useCallback((screen: Screen) => { window.location.hash = `#/${screen.toLowerCase()}` }, [])
  const shared: Shared = { go, scenarioId, setScenarioId, strategyId, setStrategyId }
  const chrome = useData(['meta', 'mbs', 'portfolio'])
  const date = chrome.state === 'ok' ? fmtDate(chrome.data.meta.data_date) : null

  return (
    <div className="frame">
      <header className="site-header pad">
        <div className="brand-row">
          <p className="brand">Tenorwise</p>
          <span className="strap">Interest-rate risk and hedging</span>
          {date && (
            <span className="tag tag-neutral date-chip"><CalendarBlank weight="duotone" size={14} /> Market data as of {date}</span>
          )}
        </div>
        <nav aria-label="Screens">
          <div className="screens">
            {SCREENS.map((s) => (
              <a key={s} href={`#/${s.toLowerCase()}`} aria-current={s === route.screen ? 'page' : undefined}>{s}</a>
            ))}
          </div>
        </nav>
      </header>

      <main className="main pad">
        {route.screen === 'Overview' && <Overview shared={shared} onAsk={(q) => { analyst.ask(q); go('Analyst') }} />}
        {route.screen === 'Curve' && <Curve shared={shared} />}
        {route.screen === 'Portfolio' && <Portfolio />}
        {route.screen === 'Scenarios' && <Scenarios shared={shared} />}
        {route.screen === 'Hedging' && <Hedging shared={shared} />}
        {route.screen === 'Analyst' && <Analyst analyst={analyst} />}
        {route.screen === 'Evidence' && <Evidence />}
        {route.screen === 'About' && <About docId={route.sub} />}
      </main>

      <footer className="site-footer pad">
        <p>
          Stylized mortgage pool. IG corporates are a proxy. Not any bank's actual holdings. Not investment advice.
          {date && ` Market data as of ${date}.`}
        </p>
        <p>
          This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.
          By using Tenorwise you agree to the{' '}
          <a href="https://fred.stlouisfed.org/docs/api/terms_of_use.html">FRED® API Terms of Use</a>.
        </p>
        {chrome.state === 'ok' && (
          <p>
            {chrome.data.mbs.mortgage_rate.attribution}{' '}
            <a href={chrome.data.portfolio.source.url}>{chrome.data.portfolio.source.text}</a>
          </p>
        )}
      </footer>
    </div>
  )
}
