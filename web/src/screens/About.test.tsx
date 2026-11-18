// About page (PLAN.md section 11, Phase 10; restyled in Phase 11). Rendered to static HTML; no browser needed.
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import committedCsv from '../../../docs/strategy/effort-timings.csv?raw'
import { STRATEGY_DOCS } from '../strategy/docs'
import { parseTimings } from '../strategy/effort'
import { About, EffortTimings } from './About'

const HEADER = 'task_id,method,date,start_time,end_time,completed,matches_engine,notes\n'
const escape = (s: string) => s.replace(/&/g, '&amp;').replace(/'/g, '&#x27;')

describe('effort timings', () => {
  it('says the study was not run while the CSV has no rows (D-081)', () => {
    const html = renderToStaticMarkup(<EffortTimings csv={HEADER} />)
    expect(html).toContain('Study not run')
    expect(html).toContain('has not been measured')
    expect(html).not.toContain('<table')
  })

  it('follows the committed CSV: not run until it has rows', () => {
    const html = renderToStaticMarkup(<EffortTimings csv={committedCsv} />)
    expect(html.includes('Study not run')).toBe(parseTimings(committedCsv).rows.length === 0)
  })

  it('computes minutes from start and end, and keeps quoted notes intact', () => {
    const csv = HEADER + 'T1,manual,2026-11-20,09:05,09:47,yes,yes,"used FRED, then a calculator"\nT1,tool,2026-11-20,10:00,10:03,yes,yes,\n'
    const { rows, errors } = parseTimings(csv)
    expect(errors).toEqual([])
    expect(rows.map((r) => [r.task_id, r.method, r.minutes])).toEqual([['T1', 'manual', 42], ['T1', 'tool', 3]])
    expect(rows[0].notes).toBe('used FRED, then a calculator')
    const html = renderToStaticMarkup(<EffortTimings csv={csv} />)
    expect(html).not.toContain('Study not run')
    expect(html).toContain('one non-expert')
    expect(html).toContain('<td>42</td>')
  })

  it('reports malformed rows instead of using them', () => {
    const csv = HEADER + 'T2,manual,2026-11-20,10:30,10:10,yes,no,\nT3,robot,2026-11-20,10:00,10:05,yes,no,\nT4,tool,20/11/2026,10:00,10:05,maybe,no,\n'
    const { rows, errors } = parseTimings(csv)
    expect(rows).toEqual([])
    expect(errors).toHaveLength(3)
  })

  it('rejects a file whose header is not the agreed columns', () => {
    expect(parseTimings('task,minutes\nT1,5\n').errors[0]).toMatch(/header/)
  })
})

describe('About page', () => {
  it('renders every strategy document from docs/strategy', () => {
    expect(STRATEGY_DOCS.map((d) => d.id)).toEqual(['opportunity-map', 'effort', 'model-memo', 'risk-controls', 'rollout-plan', 'decision-log'])
    for (const doc of STRATEGY_DOCS) {
      const html = renderToStaticMarkup(<About docId={doc.id} />)
      const firstHeading = doc.markdown.match(/^# (.+)$/m)?.[1]
      expect(firstHeading, doc.id).toBeTruthy()
      expect(html).toContain(escape(firstHeading!))
    }
  })

  it('lists six strategy pages and four reference pages', () => {
    const html = renderToStaticMarkup(<About docId={null} />)
    expect(html.match(/href="#\/about\//g)).toHaveLength(10)
  })

  it('shows the required statements', () => {
    expect(renderToStaticMarkup(<About docId="opportunity-map" />))
      .toContain('reasoned judgments from public sources, not measurements or practitioner interviews')
    expect(renderToStaticMarkup(<About docId="rollout-plan" />)).toContain('has not been executed')
    expect(renderToStaticMarkup(<About docId="effort" />)).toContain('Study not run')
  })
})
