# Assumptions

Every simplifying assumption the model makes, where it is used, and its likely
effect. Anything whose result appears in the interface is labelled there too.
Effects described as "not measured" have not been quantified; none of these
statements is a measurement unless it says so.

| ID | Assumption (plain English) | Where used | Likely effect | Phase |
|---|---|---|---|---|
| A-01 | Time is counted in whole months: a cash flow n months away is n/12 years away. There are no day-count conventions, holidays or settlement delays. | Everywhere (`tenorwise/curve/bootstrap.py`; later all instruments) | Cash-flow timing differs from real market conventions by days. This gives small price differences against market quotes (not measured). | 1 |
| A-02 | FRED's constant-maturity Treasury yields (DGS1MO to DGS30) are treated as par yields on a semiannual bond-equivalent basis. | `tenorwise/curve/fred.py`, `bootstrap.py` | The H.15 yields come from the Treasury's own fitted curve, not from individual traded bonds. Differences between particular issues (on/off-the-run, liquidity) are ignored. | 1 |
| A-03 | Tenors of 6 months and under are one payment with simple interest: DF = 1/(1 + y·T). | `bootstrap.py` | The short end follows a different compounding convention from the rest. On a flat 4% curve, the 1M and 3M zero rates are 3.3 bp and 2.0 bp above the level from 6 months on (calculated from the formulas). Owner decision pending (D-021). | 1 |
| A-04 | Zero rates are continuously compounded, linear in time between the 11 curve points, and flat before 1 month and beyond 30 years. | `bootstrap.py` (`ZeroCurve.zero_rate`) | Implied forward rates jump at each curve point. Cash flows beyond 30 years are discounted at the 30-year zero rate. | 1 |
| A-05 | The market data date is the latest date on which all 11 series have a value. Nothing is filled forward, and data more than 7 days older than the build fails the build. | `fred.py` (`select_par_curve`) | If one series is missing on the latest day, every tenor uses the earlier complete date. | 1 |
| A-06 | A rate shock is added to the 11 par yields, and the zero curve is rebuilt from scratch. | `tenorwise/curve/shocks.py` | A shock to one region's par yields also moves zero rates elsewhere through the bootstrap. On the 16 Nov 2026 curve, +25 bp on the 10-year tent lowers the 30-year zero rate by 13.6 bp (computed by the engine). | 1 |
| A-07 | Shocked par yields are floored at 0%, and the output flags when the floor binds. | `shocks.py` (`apply_shock`) | Large downward shocks on a low-rate curve are cut off at zero. Negative-rate scenarios cannot be represented. | 1 |
| A-08 | Key-rate shocks use straight-line tents at 2, 5, 10 and 30 years that sum to 1 at every tenor. | `shocks.py` (`tent_weight`) | Risk at maturities between the nodes is split between the two neighbouring buckets in straight-line proportion. | 1 |
