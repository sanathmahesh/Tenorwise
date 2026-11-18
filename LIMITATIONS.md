# Limitations

What Tenorwise cannot tell you, and why.

## Evidence

- **The provider probe is one run, from one machine, on one day** (2026-11-18 UTC;
  [docs/provider-probe.md](docs/provider-probe.md)). It shows that each model
  can do the required things. It says nothing about how reliably they do them,
  or about latency in general. Reliability and latency are measured in Phase 9.

## Yield curve

- **Eleven points and straight lines between them.** The curve knows rates at
  only 11 maturities. In between it draws straight lines in zero rate, so
  implied forward rates jump at each curve point. That is adequate for
  valuing fixed cash flows. It is not adequate for anything sensitive to
  forward rates between points, which Tenorwise does not price.
- **Not a traded-bond curve.** FRED's constant-maturity yields come from the
  Treasury's own fitted par curve. Tenorwise does not reproduce the
  Treasury's fitting method, and it ignores differences between individual
  bonds such as liquidity and on-the-run premia.
- **One day's curve.** Each build uses a single end-of-day curve; there is no
  intraday data and no rate history. The only historical input is the 2022
  replay scenario, added in Phase 5.
- **Nothing beyond 30 years.** Rates past 30 years are held flat at the
  30-year zero rate.
- **No negative rates.** Shocked par yields are floored at 0%, with a flag.
- **Key-rate shocks spill over.** Shocks are applied to par yields and the
  curve is rebuilt. Bumping one region therefore moves zero rates in other
  regions, sometimes in the opposite direction (see ASSUMPTIONS.md, A-06).
  Key-rate risk is measured in "par-yield bucket" terms, not as independent
  moves of zero rates.
- **Short-end convention.** Tenors of 6 months and under use simple interest
  while longer tenors use semiannual compounding, so even a flat par curve
  gives a slightly non-flat zero curve below 6 months (ASSUMPTIONS.md, A-03).
