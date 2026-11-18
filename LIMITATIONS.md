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

## Bonds and risk measures

- **No credit risk, no call options.** Bonds always pay in full and on
  schedule. Spreads are constant, so Tenorwise cannot show losses from
  spreads widening, only from Treasury rates moving.
- **Duration and convexity are local measures.** They describe small moves.
  For a 100 bp move, duration plus convexity was within 1.54% of a full
  reprice on the test grid, but for large scenarios the full reprice
  (Phase 5) is the number to trust.
- **Two meanings of "rate risk".** The headline duration and DV01 measure
  sensitivity to a 1 bp move in *par yields*. Modified duration measures
  sensitivity to the bond's own *yield*. On the 16 Nov 2026 curve they
  differ by up to 4.45% for long zero-coupon bonds (measured). They are not
  interchangeable, and the interface labels which is which.
- **Key-rate buckets are not independent.** Because shocks act on par
  yields, one bucket's bump moves zero rates in neighbouring regions. A bond
  can show small negative risk in a bucket. The 10y 3m bond does at 2 and 5
  years, because those bumps lower the bootstrapped zero rate near 10 years,
  where its principal is paid. The buckets still sum to the total.

