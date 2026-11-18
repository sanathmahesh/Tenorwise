"""Pay-fixed interest rate swap (PLAN.md section 7).

Swap curve = Treasury zero curve + a flat spread (default 0). Fixed leg
semiannual. Per unit notional:
    K = (1 - DF(T)) / (0.5 * sum DF(t_i))
    value to the fixed payer = (1 - DF(T)) - K * 0.5 * sum DF(t_i)
"""

import pytest

from tenorwise.analytics.risk import build_risk_curves, risk_measures
from tenorwise.curve.bootstrap import bootstrap
from tenorwise.curve.fixture import fixture_par_curve
from tenorwise.curve.shocks import apply_shock, parallel_shock
from tenorwise.instruments.swap import PayFixedSwap, annuity, float_rate_3m, par_swap_rate

TENORS = (24, 60, 120)


@pytest.fixture(scope="module")
def par():
    return fixture_par_curve()


@pytest.fixture(scope="module")
def base(par):
    return bootstrap(par)


@pytest.mark.parametrize("months", TENORS)
@pytest.mark.parametrize("spread", [0.0, 0.0025])
def test_a_new_swap_is_worth_zero(base, months, spread):
    swap = PayFixedSwap.at_par(base, months, notional=1.0, swap_spread=spread)

    assert abs(swap.value(base)) < 1e-12


@pytest.mark.parametrize("months", TENORS)
def test_with_zero_spread_the_par_swap_rate_is_the_par_yield(base, months):
    """A par swap's fixed leg is a par bond, so at curve pillars K equals the par yield."""
    y = base.par.par_yields[base.par.tenor_months.index(months)]
    assert par_swap_rate(base, months, 0.0) == pytest.approx(y, abs=1e-14)


@pytest.mark.parametrize("months", TENORS)
@pytest.mark.parametrize("bp", [1.0, 100.0])
def test_the_fixed_payer_gains_when_rates_rise(par, base, months, bp):
    swap = PayFixedSwap.at_par(base, months, notional=1.0)
    up = apply_shock(par, parallel_shock(bp)).curve
    down = apply_shock(par, parallel_shock(-bp)).curve

    assert swap.value(up) > 0
    assert swap.value(down) < 0


@pytest.mark.parametrize("months", TENORS)
def test_swap_dv01_matches_bump_and_reprice(par, base, months):
    """Bump DV01 (central +/-1 bp on par yields, curve rebuilt) against the
    formula DV01 = notional * annuity * 1 bp. Negative: the payer gains when
    rates rise. Tolerance 1e-6 relative, fixed in advance (second-order gap)."""
    notional = 1_000.0
    swap = PayFixedSwap.at_par(base, months, notional=notional)
    r = risk_measures(swap.value, build_risk_curves(par))

    assert r.dv01 < 0
    assert -r.dv01 == pytest.approx(notional * annuity(base, months, 0.0) * 1e-4, rel=1e-6)


def test_float_rate_is_the_3m_simple_rate_on_the_swap_curve(base):
    df = base.discount_factor(0.25)
    assert float_rate_3m(base, 0.0) == pytest.approx((1 / df - 1) / 0.25, abs=1e-15)


def test_swap_carry_is_notional_times_float_minus_fixed(base):
    swap = PayFixedSwap.at_par(base, 60, notional=500.0)
    assert swap.carry_12m(base) == pytest.approx(500.0 * (float_rate_3m(base, 0.0) - swap.fixed_rate), abs=1e-12)
