// Formatting, number links and chart scales (Phase 11). The design's display formats are in
// design/handoff/README.md; only the formats are taken from it, never a figure.
import { describe, expect, it } from 'vitest'
import {
  fmtBp, fmtCost, fmtDate, fmtFraction, fmtMoney, fmtMoney2, fmtNum, fmtPct, fmtSci, fmtSeconds, fmtYears, MINUS, tenorLabel, typo,
} from './format'
import { halfPointDomain, heatTint, paddedExtent, sqrtMaturity } from './scales'
import { linkNumbers, valueTagFromHref } from './tags'

describe('format', () => {
  it('money in millions, one decimal, thousands separator, true minus sign', () => {
    expect(fmtMoney(9_412_600_000)).toBe('$9,412.6M')
    expect(fmtMoney(-545_800_000)).toBe(`${MINUS}$545.8M`)
    expect(fmtMoney(179_200_000, { signed: true })).toBe('+$179.2M')
    expect(fmtMoney(-30_000, { signed: true })).toBe('$0.0M') // rounds to zero: no sign
  })
  it('DV01 in millions with two decimals', () => {
    expect(fmtMoney2(3_875_730.6)).toBe('$3.88M')
    expect(fmtMoney2(-1_204_582)).toBe(`${MINUS}$1.20M`)
  })
  it('percent, basis points, years and plain numbers', () => {
    expect(fmtPct(3.781)).toBe('3.78%')
    expect(fmtPct(-4.2851, { signed: true })).toBe(`${MINUS}4.29%`)
    expect(fmtPct(23.0, { decimals: 1 })).toBe('23.0%')
    expect(fmtBp(100)).toBe('+100 bp')
    expect(fmtBp(-50)).toBe(`${MINUS}50 bp`)
    expect(fmtBp(0)).toBe('0 bp')
    expect(fmtYears(4.2149)).toBe('4.21 years')
    expect(fmtNum(-137.2308)).toBe(`${MINUS}137.23`)
  })
  it('evidence: fractions as one-decimal percent, ms as seconds, cost to three significant figures', () => {
    expect(fmtFraction(0.97222)).toBe('97.2%')
    expect(fmtFraction(1)).toBe('100.0%')
    expect(fmtSeconds(4687)).toBe('4.7 s')
    expect(fmtCost(0.00021135638)).toBe('$0.000211')
    expect(fmtCost(0.002472948)).toBe('$0.00247')
    expect(fmtCost(0.006906119)).toBe('$0.00691')
    expect(fmtCost(0.031)).toBe('$0.0310')
  })
  it('dates and tiny differences', () => {
    expect(fmtDate('2026-11-16')).toBe('16 Nov 2026')
    expect(fmtDate('2026-01-05')).toBe('5 Jan 2026')
    expect(fmtSci(1.5386303342523888e-13)).toBe('1.5 × 10⁻¹³')
    expect(fmtSci(7.077671781985373e-16)).toBe('7.1 × 10⁻¹⁶')
    expect(fmtSci(0)).toBe('0')
  })
  it('typographic minus in names from the data', () => {
    expect(typo('-100 bp parallel')).toBe(`${MINUS}100 bp parallel`)
    expect(typo('Custom: -50 bp parallel')).toBe(`Custom: ${MINUS}50 bp parallel`)
    expect(typo('Key-rate-matched hedge')).toBe('Key-rate-matched hedge')
  })
  it('tenor labels', () => {
    expect(tenorLabel(1 / 12)).toBe('1 month')
    expect(tenorLabel(0.5)).toBe('6 months')
    expect(tenorLabel(1)).toBe('1 year')
    expect(tenorLabel(30)).toBe('30 years')
  })
})

describe('number links', () => {
  it('turns each tagged number into a link to its value', () => {
    expect(linkNumbers('falls by -$370.6M[[v11]], out of $8.65B[[v1]].'))
      .toBe('falls by [-$370.6M](#value-v11), out of [$8.65B](#value-v1).')
  })
  it('keeps units, signs and parentheses with the number', () => {
    expect(linkNumbers('a 4.29%[[v3]] fall')).toBe('a [4.29%](#value-v3) fall')
    expect(linkNumbers('DV01 of $3.9M per bp[[v6]]')).toBe('DV01 of [$3.9M per bp](#value-v6)')
    expect(linkNumbers('lasts 6.19 years[[v2]]')).toBe('lasts [6.19 years](#value-v2)')
    expect(linkNumbers('77.0 bp[[v4]]')).toBe('[77.0 bp](#value-v4)')
    expect(linkNumbers('(2.3%)[[v5]]')).toBe('[(2.3%)](#value-v5)')
    expect(linkNumbers('−$370.6M[[v9]]')).toBe('[−$370.6M](#value-v9)')
    expect(linkNumbers('a price of 104.33[[v8]]')).toBe('a price of [104.33](#value-v8)')
  })
  it('links a tag with no number before it as "source"', () => {
    expect(linkNumbers('see the table[[v7]]')).toBe('see the table [source](#value-v7)')
  })
  it('reads the tag back from a link', () => {
    expect(valueTagFromHref('#value-v12')).toBe('v12')
    expect(valueTagFromHref('https://example.com')).toBeNull()
  })
})

describe('scales', () => {
  it('maturity axis is the square root of years over 30', () => {
    expect(sqrtMaturity(30)).toBe(1)
    expect(sqrtMaturity(7.5)).toBeCloseTo(0.5)
  })
  it('percent axes pad to the nearest half point', () => {
    expect(halfPointDomain([4.1, 5.51])).toEqual([4, 6])
    expect(halfPointDomain([4.0, 4.0])).toEqual([3.5, 4.5])
  })
  it('scatter axes include zero and add 12% padding', () => {
    const [lo, hi] = paddedExtent([10, 30])
    expect(lo).toBeCloseTo(-3.6)
    expect(hi).toBeCloseTo(33.6)
    expect(paddedExtent([0, 0])).toEqual([-1, 1])
  })
  it('heatmap tint grows with the square root of size, capped at 55%', () => {
    expect(heatTint(100, 100)).toBe(55)
    expect(heatTint(-25, 100)).toBe(28)
    expect(heatTint(0, 100)).toBe(0)
    expect(heatTint(5, 0)).toBe(0)
  })
})
