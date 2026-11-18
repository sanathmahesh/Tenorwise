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

## Agency mortgage bonds (stylized)

- **Stylized, not calibrated.** The prepayment curve's four parameters are
  illustrative. Tenorwise shows *how* mortgage bonds behave, not what a real
  pool is worth or how fast it will prepay.
- **Static valuation.** One cash-flow projection per scenario, with no rate
  uncertainty. That misses the time value of the borrower's prepayment
  option, which an option-adjusted spread (OAS) model would capture.
- **Missing prepayment effects:** burnout (pools that have already passed up
  refinancing chances stay slow), seasonality, house-price and cash-out
  effects, loan-size and credit differences.
- **A fixed mortgage spread.** Mortgage rates move one-for-one with the
  10-year Treasury in every scenario. In real stress the spread can widen
  sharply.
- **The edges of the S-curve.** Beyond about +50 bp prepayments sit at their
  floor and duration drifts down as rates rise. In deep rallies they sit at
  their ceiling and duration rises again as rates fall. A pool priced well
  above par can even show negative duration. These follow from the model's
  assumptions, not from market behaviour.
- **One product.** Only 30-year conforming fixed-rate pools. No 15-year
  pools, adjustable-rate mortgages, multifamily, or structured mortgage
  securities.

## Portfolio

- **Not BNY's portfolio.** The mix follows BNY's 10-Q, but the 38 positions
  are design choices, and 27.2% of BNY's securities (non-US government bonds
  and CLOs) are left out.
- **Reported losses are not comparable to BNY's.** BNY applies fair-value
  hedge accounting to about $61B of AFS securities, which shrinks its
  reported AFS losses. Its real holdings also differ from stylized pools. On
  16 Nov 2026 the model book shows −13.5% unrealized against −4.0% for BNY's
  whole portfolio at 30 Sept 2026. That is a difference in construction, not
  a measurement of BNY.
- **One yield per bucket.** Every position in a BNY line and maturity bucket
  gets that bucket's average yield, so the spread of yields inside a bucket
  is lost.
- **The IG proxy is not covered bonds.** It ignores currency, structure and
  amortization.
- **No credit, tax or funding.** Spreads never move, AOCI is pre-tax, and
  carry (Phase 5) ignores funding cost.

## Scenarios

- **Instantaneous and static.** Each scenario is a single jump in rates with
  nothing happening afterwards: no time passes, bonds don't mature, and
  nothing is reinvested.
- **Spreads never move.** Real rate shocks often come with wider credit and
  mortgage spreads, which would add losses that Tenorwise does not show.
- **Seven scenarios are not a distribution.** They show what *would* happen
  under specific moves, not how likely those moves are. There is no
  value-at-risk.
- **Carry is not earnings.** It is interest income on today's holdings at
  their book yields, with no funding cost and no reinvestment at new rates.
- **The 2022 replay applies 2022's moves to today's curve.** Starting from
  5% rather than near zero, the same basis-point moves may not be plausible.

## Hedging

- **Leftover 10s-30s risk.** The key-rate hedge zeroes the 2-year and
  5-year buckets and the 10-year plus 30-year *total*. It leaves −$301k per
  bp at 10 years against +$301k at 30 years, so a move in the gap between 10-
  and 30-year rates is unhedged.
- **Static hedges.** Hedges are never rebalanced. In a −200 bp rally the
  mortgage pools prepay, the AFS book's duration shortens, and the full DV01
  hedge loses $13.1M where convexity alone predicts a $15.8M gain.
- **Idealised hedge accounting.** Swaps are assumed perfectly effective.
  Real hedge accounting has ineffectiveness and strict designation and
  documentation rules.
- **HTM is not hedged.** Under current US GAAP (ASC 815-20-25-43) HTM
  interest-rate risk cannot be a hedged risk. FASB proposed changing this on
  17 June 2026 (comments closed 17 August 2026). Whether it has since become
  final is not confirmed here.
- **No real swap curve.** Swaps are priced on the Treasury curve plus a
  fixed spread (0 by default). There is no SOFR curve, no swap-spread risk,
  and no collateral, margin, counterparty or transaction costs.
- **Carry given up assumes the floating rate stays fixed** for 12 months at
  the scenario's 3-month rate.

## Snapshot and API

- **One snapshot per deploy.** Market data is fetched when the site is built.
  Until the next deploy, every page shows that day's data, with its date.
- **Custom scenarios are limited.** Only a parallel shift or key-rate shocks
  of −300 to +300 bp, recomputed on the build's market data. There is no
  intraday data and no user-chosen curve.
- **Rounded figures.** Published numbers are rounded to 10 significant
  figures (dollar precision on a $10B book).
- **Placeholder interface.** Phase 7's pages are plain tables. The designed
  interface arrives in Phase 11.

## AI analyst and verification

- **Verification proves each number came from the engine and was copied
  correctly, not that the sentence around it is right.** A correct figure can
  be attached to the wrong claim, for example the portfolio's DV01 described as
  the AFS book's. Phase 9 measures how often answers pass verification but are
  wrong.
- **Numbers written as words** ("two hundred") are not detected by the
  verifier. The system prompt asks for display strings.
- **Context numbers can be stated untagged:** tenors, shock sizes, hedge
  ratios, the 12-month horizon and dates. A model could misuse one, for
  example "100" in the wrong sense, without failing verification.
- **The analyst explains the engine; it adds no judgment.** It cannot
  forecast, give investment advice, or answer about securities outside the
  model book. It is asked to decline those, and Phase 9 tests that it does.
- **Rate limits are per IP.** Someone with many IP addresses can use more than
  the per-IP cap. The global daily cap bounds the total cost regardless.
- **Cost figures are computed, not billed.** They come from token usage at
  list prices read on 2026-11-17. They are an upper bound if the provider
  does not report cached tokens.

