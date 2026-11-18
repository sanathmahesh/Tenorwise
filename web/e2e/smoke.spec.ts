// Browser smoke test of each screen and each Analyst state (PLAN.md Phase 11).
// Static data and API responses come from web/e2e/fixtures, which scripts/make_web_fixtures.py
// generates from the real engine and agent loop. Expected strings are computed from those files
// with the app's own formatters; no figure is typed here.
import { expect, test, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { fmtCost, fmtDate, fmtFraction, fmtMoney } from '../src/lib/format'

const FIX = new URL('./fixtures/', import.meta.url)
const dataPath = (f: string) => fileURLToPath(new URL(`data/${f}`, FIX))
const data = (f: string) => JSON.parse(readFileSync(dataPath(f), 'utf8'))
const apiBody = (f: string) => readFileSync(fileURLToPath(new URL(`api/${f}`, FIX)), 'utf8')

const meta = data('meta.json')
const portfolio = data('portfolio.json')
const scenarios = data('scenarios.json')
const hedges = data('hedges.json')
const evidence = data('evidence.json')

async function serveData(page: Page, failing: string[] = []) {
  await page.route('**/data/v1/*.json', (route) => {
    const name = new URL(route.request().url()).pathname.split('/').pop()!
    if (failing.includes(name)) return route.fulfill({ status: 500, body: 'fail' })
    return route.fulfill({ path: dataPath(name), contentType: 'application/json' })
  })
}

function watchErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
  return errors
}

async function open(page: Page, screen: string) {
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Screens' }).getByRole('link', { name: screen, exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: screen })).toBeVisible()
}

test.beforeEach(async ({ page }) => { await serveData(page) })

// ------------------------------------------------------------------ shell

test('header, navigation and footer carry the data date and required notices', async ({ page }) => {
  const errors = watchErrors(page)
  await page.goto('/')
  await expect(page.getByText(`Market data as of ${fmtDate(meta.data_date)}`).first()).toBeVisible()
  const nav = page.getByRole('navigation', { name: 'Screens' })
  for (const s of ['Overview', 'Curve', 'Portfolio', 'Scenarios', 'Hedging', 'Analyst', 'Evidence', 'About']) {
    await expect(nav.getByRole('link', { name: s, exact: true })).toBeVisible()
  }
  const footer = page.getByRole('contentinfo')
  await expect(footer).toContainText('This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.')
  await expect(footer.getByRole('link', { name: 'FRED® API Terms of Use' })).toHaveAttribute('href', 'https://fred.stlouisfed.org/docs/api/terms_of_use.html')
  await expect(footer).toContainText(data('mbs.json').mortgage_rate.attribution)
  await expect(footer.getByRole('link', { name: portfolio.source.text })).toHaveAttribute('href', portfolio.source.url)
  expect(errors).toEqual([])
})

// ------------------------------------------------------------------ screens

test('Overview shows the summary figures and opens Hedging on a scenario', async ({ page }) => {
  const errors = watchErrors(page)
  await open(page, 'Overview')
  await expect(page.getByText(fmtMoney(portfolio.summary.market_value)).first()).toBeVisible()
  await expect(page.getByText(fmtMoney(portfolio.summary.unrealized)).first()).toBeVisible()
  const strip = page.getByRole('list', { name: 'Scenarios' })
  await expect(strip.getByRole('listitem')).toHaveCount(scenarios.scenarios.length - 1)
  const replay = scenarios.scenarios.find((s: { id: string }) => s.id === 'replay_2022')
  await strip.getByRole('button', { name: new RegExp(replay.name) }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Hedging' })).toBeVisible()
  expect(errors).toEqual([])
})

test('Curve shows the 11 maturities and overlays a scenario', async ({ page }) => {
  const errors = watchErrors(page)
  await open(page, 'Curve')
  await expect(page.getByRole('table', { name: 'The 11 maturities' }).locator('tbody tr')).toHaveCount(11)
  await page.getByRole('button', { name: '+100 bp parallel', exact: true }).click()
  await expect(page.getByText('Par after +100 bp parallel')).toBeVisible()
  expect(errors).toEqual([])
})

test('Portfolio lists every position, labels stylized pools and opens the drawer', async ({ page }) => {
  const errors = watchErrors(page)
  await open(page, 'Portfolio')
  const table = page.getByRole('table', { name: 'Positions' })
  await expect(table.locator('tbody tr')).toHaveCount(portfolio.positions.length)
  const stylized = portfolio.positions.filter((p: { stylized: boolean }) => p.stylized).length
  await expect(table.getByText('Stylized', { exact: true })).toHaveCount(stylized)
  await expect(page.getByRole('heading', { name: /Mortgages/ })).toContainText('Stylized')
  const first = portfolio.positions[0]
  await table.getByRole('button', { name: first.name }).click()
  const drawer = page.getByRole('dialog', { name: first.name })
  await expect(drawer).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  expect(errors).toEqual([])
})

test('Scenarios shows a preset and prices a custom scenario on the engine', async ({ page }) => {
  const errors = watchErrors(page)
  const custom = JSON.parse(apiBody('scenario-parallel-50.json'))
  let sent: unknown = null
  await page.route('**/api/scenario', async (route) => {
    sent = route.request().postDataJSON()
    await route.fulfill({ status: 200, contentType: 'application/json', body: apiBody('scenario-parallel-50.json') })
  })
  await open(page, 'Scenarios')
  const up100 = scenarios.scenarios.find((s: { id: string }) => s.id === 'parallel_up_100')
  await expect(page.getByText(fmtMoney(up100.total.delta_mv, { signed: true })).first()).toBeVisible()
  await page.getByRole('slider', { name: 'All rates' }).fill('50')
  await page.getByRole('button', { name: 'Price scenario' }).click()
  await expect(page.getByRole('heading', { name: custom.scenario.name })).toBeVisible()
  await expect(page.getByText(fmtMoney(custom.scenario.total.delta_mv, { signed: true })).first()).toBeVisible()
  expect(sent).toEqual({ parallel_bp: 50 })
  expect(errors).toEqual([])
})

test('Hedging shows the strategy-by-scenario grid, the scatter and the hedge composition', async ({ page }) => {
  const errors = watchErrors(page)
  await open(page, 'Hedging')
  const grid = page.getByRole('table', { name: 'Net change after the hedge' })
  await expect(grid.locator('tbody tr')).toHaveCount(hedges.strategies.length)
  await expect(grid.locator('tbody td')).toHaveCount(hedges.strategies.length * (scenarios.scenarios.length - 1))
  await expect(page.getByRole('img', { name: /Loss avoided against carry given up/ }).locator('circle')).toHaveCount(hedges.strategies.length)
  const full = hedges.strategies.find((s: { id: string }) => s.id === 'dv01_full')
  await grid.getByRole('button', { name: full.name }).click()
  await expect(page.getByRole('table', { name: 'Hedge composition' })).toContainText(fmtMoney(full.swaps[0].notional))
  await expect(page.getByText(/swap spread/i).first()).toBeVisible()
  expect(errors).toEqual([])
})

test('Evidence shows each model, marks the production model and lists every question', async ({ page }) => {
  const errors = watchErrors(page)
  await open(page, 'Evidence')
  for (const m of evidence.models) {
    const block = page.getByRole('region', { name: m.id })
    await expect(block).toContainText(fmtFraction(m.accuracy))
    await expect(block).toContainText(fmtCost(m.cost_per_question_usd))
  }
  await expect(page.getByRole('region', { name: meta.llm_model })).toContainText('In production')
  await expect(page.getByRole('table', { name: 'Results by question' }).locator('tbody tr')).toHaveCount(evidence.questions.length)
  await expect(page.getByRole('table', { name: 'Agreement with QuantLib' }).locator('tbody tr')).toHaveCount(evidence.quantlib.length)
  expect(errors).toEqual([])
})

test('About renders the strategy files, the reference pages and the not-run timings state', async ({ page }) => {
  const errors = watchErrors(page)
  await open(page, 'About')
  const pages = page.getByRole('navigation', { name: 'About pages' }).getByRole('link')
  await expect(pages).toHaveCount(10)
  await expect(page.getByRole('heading', { level: 1, name: 'Opportunity map' }).last()).toBeVisible()
  await pages.getByText('Effort', { exact: true }).click()
  await expect(page.getByText('Study not run')).toBeVisible()
  await pages.getByText('Limitations', { exact: true }).click()
  await expect(page.locator('article')).toContainText('Verification proves each number came from the engine')
  await pages.getByText('Assumptions', { exact: true }).click()
  await expect(page.locator('article').getByRole('row')).toHaveCount(meta.assumptions.length + 1)
  expect(errors).toEqual([])
})

test('a screen whose data fails to load says so and can retry', async ({ page }) => {
  await page.unrouteAll()
  await serveData(page, ['portfolio.json'])
  await open(page, 'Portfolio')
  await expect(page.getByText('Could not load')).toBeVisible()
  await page.unrouteAll()
  await serveData(page)
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.getByRole('table', { name: 'Positions' })).toBeVisible()
})

// ------------------------------------------------------------------ Analyst states

async function mockAsk(page: Page, status: number, body: string, delayMs = 0) {
  await page.route('**/api/agent/ask', async (route) => {
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs))
    await route.fulfill({ status, contentType: 'application/json', body })
  })
}

async function ask(page: Page, question = 'How much does the portfolio lose if rates rise 100 bp?') {
  await page.getByRole('textbox', { name: 'Question' }).fill(question)
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
}

test('Analyst idle state offers suggested questions', async ({ page }) => {
  await open(page, 'Analyst')
  await expect(page.getByRole('list', { name: 'Suggested questions' }).getByRole('button')).toHaveCount(6)
  await expect(page.getByRole('button', { name: 'Draft portfolio commentary' })).toBeEnabled()
})

test('Analyst loading, then answered with number links that open their provenance', async ({ page }) => {
  const errors = watchErrors(page)
  const body = JSON.parse(apiBody('ask-answered.json'))
  await mockAsk(page, 200, apiBody('ask-answered.json'), 1200)
  await open(page, 'Analyst')
  await ask(page)
  await expect(page.getByText('Checking every number against the engine')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Ask', exact: true })).toBeDisabled()
  await expect(page.getByText('Every number verified')).toBeVisible()
  await expect(page.getByText(body.verification_rule)).toBeVisible()
  const tag = Object.keys(body.values)[0]
  const value = body.values[tag]
  await page.getByRole('button', { name: new RegExp(`^${value.display.replace(/[$.]/g, '\\$&').replace('-', '[-−]')}`) }).first().click()
  const panel = page.getByRole('dialog', { name: 'Where this number comes from' })
  await expect(panel).toContainText(value.label)
  await expect(panel).toContainText(value.tool)
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()
  expect(errors).toEqual([])
})

test('Analyst cannot-answer state', async ({ page }) => {
  await mockAsk(page, 200, apiBody('ask-cannot-answer.json'))
  await open(page, 'Analyst')
  await ask(page, 'Where will the 10-year yield be next year?')
  await expect(page.getByText('The analyst declined this question')).toBeVisible()
  await expect(page.getByText(JSON.parse(apiBody('ask-cannot-answer.json')).answer_md)).toBeVisible()
})

test('Analyst blocked state shows the engine table and no prose', async ({ page }) => {
  const body = JSON.parse(apiBody('ask-blocked.json'))
  await mockAsk(page, 200, apiBody('ask-blocked.json'))
  await open(page, 'Analyst')
  await ask(page, 'How big is the book?')
  await expect(page.getByText('Blocked: verification failed')).toBeVisible()
  await expect(page.getByRole('table', { name: 'Engine figures' }).locator('tbody tr')).toHaveCount(body.fallback.length)
  await expect(page.getByText('The book is worth')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Ask again' })).toBeVisible()
})

test('Analyst daily-limit state (HTTP 429)', async ({ page }) => {
  await mockAsk(page, 429, JSON.stringify({ detail: 'Daily limit reached for this address.' }))
  await open(page, 'Analyst')
  await ask(page)
  await expect(page.getByText('Daily limit reached').first()).toBeVisible()
})

test('Analyst error states: unavailable (HTTP 503) and a failed model call', async ({ page }) => {
  await mockAsk(page, 503, JSON.stringify({ detail: 'AI temporarily unavailable' }))
  await open(page, 'Analyst')
  await ask(page)
  await expect(page.getByText('Something went wrong')).toBeVisible()
  await expect(page.getByText('AI temporarily unavailable')).toBeVisible()
  await page.unroute('**/api/agent/ask')
  await mockAsk(page, 200, apiBody('ask-error.json'))
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByText(JSON.parse(apiBody('ask-error.json')).error)).toBeVisible()
})

test('Analyst commentary carries the draft notice and five sections', async ({ page }) => {
  const errors = watchErrors(page)
  const body = JSON.parse(apiBody('commentary.json'))
  await page.route('**/api/agent/commentary', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: apiBody('commentary.json') }))
  await open(page, 'Analyst')
  await page.getByRole('button', { name: 'Draft portfolio commentary' }).click()
  await expect(page.getByText(body.notice)).toBeVisible()
  for (const s of body.sections) await expect(page.getByRole('heading', { name: s.heading })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Print' })).toBeVisible()
  expect(errors).toEqual([])
})

test('the Overview question box submits to the Analyst', async ({ page }) => {
  await mockAsk(page, 200, apiBody('ask-answered.json'))
  await open(page, 'Overview')
  await page.getByRole('textbox', { name: 'Ask the analyst' }).fill('How much does the portfolio lose if rates rise 100 bp?')
  await page.getByRole('button', { name: 'Ask', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Analyst' })).toBeVisible()
  await expect(page.getByText('Every number verified')).toBeVisible()
})
