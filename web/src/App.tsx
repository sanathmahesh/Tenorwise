import { useState } from 'react'
import type { Meta } from './api/types'
import { useJson } from './api/useJson'
import { AboutPage } from './pages/AboutPage'
import { AnalystPage } from './pages/AnalystPage'
import { CurvePage } from './pages/CurvePage'
import { HedgingPage } from './pages/HedgingPage'
import { MbsPage } from './pages/MbsPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { ScenariosPage } from './pages/ScenariosPage'

// Placeholder interface (Phase 7): plain pages and tables. The real design arrives in Phase 11.
const PAGES = {
  Curve: CurvePage,
  Portfolio: PortfolioPage,
  'Mortgage bonds (stylized)': MbsPage,
  Scenarios: ScenariosPage,
  Hedging: HedgingPage,
  Analyst: AnalystPage,
  About: AboutPage,
} as const
type PageName = keyof typeof PAGES

export default function App() {
  const [page, setPage] = useState<PageName>('Curve')
  const meta = useJson<Meta>('meta.json')
  const Page = PAGES[page]
  return (
    <>
      <header>
        <h1>Tenorwise</h1>
        <p>
          Market data date: {meta.state === 'ok' ? meta.data.data_date : '…'}
          {meta.state === 'ok' && ` · built ${meta.data.build_time} · ${meta.data.git_sha ?? ''}`}
        </p>
        <nav>
          {(Object.keys(PAGES) as PageName[]).map((name) => (
            <button key={name} onClick={() => setPage(name)} disabled={name === page}>{name}</button>
          ))}
        </nav>
      </header>
      <main><Page /></main>
      <footer>
        <p>
          This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.
          By using Tenorwise you agree to the <a href="https://fred.stlouisfed.org/docs/api/terms_of_use.html">FRED® API Terms of Use</a>.
        </p>
        <p>Mortgage rate: Optimal Blue Mortgage Market Indices (OBMMI™) 30-Year Fixed Rate Conforming Mortgage Index, via FRED. Portfolio mix based on BNY's Form 10-Q (quarter ended 30 September 2026); positions are design choices, not BNY's holdings.</p>
      </footer>
    </>
  )
}
