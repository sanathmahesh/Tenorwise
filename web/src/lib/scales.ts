// Chart scales from the design spec. These place marks on screen; they never produce a figure
// that is shown as a result.

/** Maturity axis on a square-root scale: sqrt(t / 30). */
export function sqrtMaturity(years: number, maxYears = 30): number {
  return Math.sqrt(years / maxYears)
}

/** A percent axis padded out to the nearest half point; never a zero-width range. */
export function halfPointDomain(values: number[]): [number, number] {
  let lo = Math.floor(Math.min(...values) * 2) / 2
  let hi = Math.ceil(Math.max(...values) * 2) / 2
  if (lo === hi) { lo -= 0.5; hi += 0.5 }
  return [lo, hi]
}

/** Scatter axes: from the smallest to the largest value, always including zero, plus 12% padding. */
export function paddedExtent(values: number[], pad = 0.12): [number, number] {
  const lo = Math.min(0, ...values)
  const hi = Math.max(0, ...values)
  const span = hi - lo
  if (span === 0) return [-1, 1]
  return [lo - pad * span, hi + pad * span]
}

/** Heatmap tint in percent: round(min(1, sqrt(|value| / largest)) x 55). */
export function heatTint(value: number, largest: number): number {
  if (!(largest > 0)) return 0
  return Math.round(Math.min(1, Math.sqrt(Math.abs(value) / largest)) * 55)
}

/** Map a value from a domain onto a pixel range. */
export function linear([d0, d1]: [number, number], [r0, r1]: [number, number]) {
  return (v: number) => (d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0))
}
