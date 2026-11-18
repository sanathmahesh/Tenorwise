// Display helpers. Contract units: US dollars, percent, years, basis points.
export const money = (usd: number) => `${usd < 0 ? '-' : ''}$${(Math.abs(usd) / 1e6).toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}M`
export const dv01 = (usdPerBp: number) => `${usdPerBp < 0 ? '-' : ''}$${Math.round(Math.abs(usdPerBp) / 1e3).toLocaleString('en-US')}k/bp`
export const pct = (x: number, digits = 2) => `${x.toFixed(digits)}%`
export const num = (x: number, digits = 2) => x.toFixed(digits)
export const bp = (x: number) => `${x >= 0 ? '+' : ''}${x.toFixed(0)} bp`
export const tenor = (years: number) => (years < 1 ? `${Math.round(years * 12)}M` : `${years}Y`)
