// Display formats from the design handoff (design/handoff/README.md, "Units, signs and formats").
// Negative numbers use the true minus sign U+2212, never brackets. Changes carry "+" when positive.
// Values are only formatted here; nothing is computed.

export const MINUS = '−'

const grouped = (x: number, decimals: number) =>
  x.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })

function sign(abs: string, value: number, signed: boolean | undefined): string {
  if (/^[^1-9]*$/.test(abs)) return abs // rounds to zero: no sign
  if (value < 0) return MINUS + abs
  return signed ? `+${abs}` : abs
}

export interface SignOpt { signed?: boolean }

/** US dollars in millions, one decimal, thousands separators: $9,412.6M */
export function fmtMoney(usd: number, o: SignOpt = {}): string {
  return sign(`$${grouped(Math.abs(usd) / 1e6, 1)}M`, usd, o.signed)
}

/** DV01 and hedge-table dollars in millions, two decimals: $0.52M */
export function fmtMoney2(usd: number, o: SignOpt = {}): string {
  return sign(`$${grouped(Math.abs(usd) / 1e6, 2)}M`, usd, o.signed)
}

/** A plain number with a true minus sign. */
export function fmtNum(x: number, decimals = 2, o: SignOpt = {}): string {
  return sign(grouped(Math.abs(x), decimals), x, o.signed)
}

/** Rates and yields already in percent: 3.78% */
export function fmtPct(pct: number, o: SignOpt & { decimals?: number } = {}): string {
  return `${fmtNum(pct, o.decimals ?? 2, o)}%`
}

/** Shocks and spreads in whole basis points, signed: +100 bp */
export function fmtBp(bp: number): string {
  return `${fmtNum(bp, 0, { signed: true })} bp`
}

export function fmtYears(years: number): string {
  return `${fmtNum(years, 2)} years`
}

/** Evidence fractions (0 to 1) as one-decimal percent: 97.2% */
export function fmtFraction(f: number): string {
  return `${(100 * f).toFixed(1)}%`
}

/** Milliseconds as seconds, one decimal: 4.7 s */
export function fmtSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`
}

/** Cost per question to three significant figures, so small costs never print as $0.000 (D-076). */
export function fmtCost(usd: number): string {
  if (usd === 0) return '$0'
  const text = Math.abs(usd) >= 1e-6 ? usd.toPrecision(3) : usd.toExponential(2)
  return usd < 0 ? `${MINUS}$${text.slice(1)}` : `$${text}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** ISO date as day, short month, year: 16 Nov 2026 */
export function fmtDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return `${d} ${MONTHS[m - 1]} ${y}`
}

const SUPERSCRIPT: Record<string, string> = {
  '-': '⁻', '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
}

/** Tiny differences (QuantLib agreement) in scientific notation: 1.5 × 10⁻¹³ */
export function fmtSci(x: number): string {
  if (x === 0) return '0'
  const [mantissa, exponent] = Math.abs(x).toExponential(1).split('e')
  const exp = String(Number(exponent)).split('').map((c) => SUPERSCRIPT[c]).join('')
  return `${x < 0 ? MINUS : ''}${mantissa} × 10${exp}`
}

/** 1/12 -> "1 month", 0.5 -> "6 months", 1 -> "1 year", 30 -> "30 years" */
export function tenorLabel(years: number): string {
  const months = Math.round(years * 12)
  if (months < 12) return `${months} month${months === 1 ? '' : 's'}`
  const y = Math.round(years * 100) / 100
  return `${y} year${y === 1 ? '' : 's'}`
}

/** Short maturity label for chart axes: 1M, 6M, 1Y, 30Y */
export function tenorShort(years: number): string {
  const months = Math.round(years * 12)
  return months < 12 ? `${months}M` : `${Math.round(years * 100) / 100}Y`
}

/** Loss / gain / neutral class for a change. */
export function tone(value: number): 'loss' | 'gain' | '' {
  return value < 0 ? 'loss' : value > 0 ? 'gain' : ''
}

/** Typographic minus for names that come from the data, e.g. "-100 bp parallel" -> "−100 bp parallel". */
export function typo(text: string): string {
  return text.replace(/(^|[\s(:])-(?=\d)/g, `$1${MINUS}`)
}
