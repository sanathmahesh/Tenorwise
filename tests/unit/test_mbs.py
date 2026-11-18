"""Stylized agency mortgage pass-through (PLAN.md section 6).

Cash-flow identities use synthetic pools. Rate-behaviour tests use the pinned
Treasury curve and the pinned mortgage spread (OBMMIC30YF - DGS10, D-031).

"A pool near current rates" (D-032): gross coupon (WAC) equal to the current
mortgage rate, so the refinancing incentive is zero; 36 months old, so the
prepayment ramp is complete; 324 months remaining; and discounted at the
spread that prices it at exactly par on the base curve (the market's sense of
a current-coupon pool).
"""

import numpy as np
import pytest

from tenorwise.analytics.risk import build_risk_curves, risk_measures
from tenorwise.curve.bootstrap import bootstrap
from tenorwise.curve.fixture import fixture_mortgage_spread, fixture_par_curve
from tenorwise.curve.shocks import apply_shock, parallel_shock
from tenorwise.instruments.bond import FixedRateBond
from tenorwise.instruments.mbs import (
    STYLIZED,
    MortgagePool,
    PrepaymentModel,
    cpr_to_smm,
    discount_spread_for_price,
    smm_to_cpr,
    ten_year_par_yield,
)

MODEL = PrepaymentModel()


# ----------------------------------------------------------- cash-flow identities


def test_zero_prepayment_gives_a_level_payment_and_the_balance_ends_at_zero():
    pool = MortgagePool(wac=0.06, remaining_term_months=360, age_months=0)
    cf = pool.project(np.zeros(360))

    np.testing.assert_allclose(cf.scheduled_payment, cf.scheduled_payment[0], rtol=1e-12)
    assert abs(cf.balance_end[-1]) < 1e-9
    assert np.all(cf.prepayment == 0.0)


@pytest.mark.parametrize("cpr", [0.0, 0.06, 0.20, 0.60, 0.99])
def test_total_principal_equals_starting_balance_at_any_speed(cpr):
    pool = MortgagePool(wac=0.065, remaining_term_months=300, age_months=60)
    cf = pool.project(np.full(300, cpr))

    assert cf.principal.sum() == pytest.approx(100.0, abs=1e-9)
    assert abs(cf.balance_end[-1]) < 1e-9


@pytest.mark.parametrize("speed", ["zero", "slow", "fast", "ramped-s-curve"])
def test_discounting_at_the_net_coupon_gives_par_at_any_speed(speed):
    pool = MortgagePool(wac=0.065, remaining_term_months=324, age_months=6)
    cprs = {
        "zero": np.zeros(324),
        "slow": np.full(324, 0.05),
        "fast": np.full(324, 0.45),
        "ramped-s-curve": pool.cpr_path(mortgage_rate=0.055, model=MODEL),
    }[speed]
    cf = pool.project(cprs)
    monthly = pool.net_coupon / 12

    pv = float(np.sum(cf.total / (1 + monthly) ** cf.months))
    assert pv == pytest.approx(100.0, abs=1e-9)


def test_cpr_and_smm_round_trip():
    cpr = np.linspace(0.0, 0.99, 100)

    np.testing.assert_allclose(smm_to_cpr(cpr_to_smm(cpr)), cpr, atol=1e-14)
    # 1 - (1 - SMM)^12 = CPR: 12 months of SMM compound to the annual rate.
    assert cpr_to_smm(0.06) == pytest.approx(1 - 0.94 ** (1 / 12), abs=1e-15)


def test_cpr_rises_with_incentive_and_stays_within_its_bounds():
    incentive = np.linspace(-5, 5, 1001)
    cpr = MODEL.seasoned_cpr(incentive)

    assert np.all(np.diff(cpr) > 0)
    assert np.all(cpr > MODEL.cpr_min) and np.all(cpr < MODEL.cpr_max)
    assert MODEL.seasoned_cpr(MODEL.x0) == pytest.approx((MODEL.cpr_min + MODEL.cpr_max) / 2, abs=1e-15)


def test_ramp_scales_cpr_until_30_months_of_age():
    assert MODEL.cpr(1.0, age_months=15) == pytest.approx(0.5 * MODEL.seasoned_cpr(1.0), abs=1e-15)
    assert MODEL.cpr(1.0, age_months=30) == MODEL.seasoned_cpr(1.0)
    assert MODEL.cpr(1.0, age_months=200) == MODEL.seasoned_cpr(1.0)


def test_model_is_labelled_stylized():
    assert STYLIZED is True
    assert MODEL.stylized_note.lower().startswith("stylized")


# ----------------------------------------------------------- behaviour under rate moves


@pytest.fixture(scope="module")
def par():
    return fixture_par_curve()


@pytest.fixture(scope="module")
def mortgage_spread():
    return fixture_mortgage_spread().spread


@pytest.fixture(scope="module")
def pool(par, mortgage_spread):
    """The pool near current rates (see module docstring)."""
    return MortgagePool(
        wac=ten_year_par_yield(bootstrap(par)) + mortgage_spread,
        remaining_term_months=324,
        age_months=36,
    )


@pytest.fixture(scope="module")
def discount_spread(par, pool, mortgage_spread):
    return discount_spread_for_price(pool, bootstrap(par), mortgage_spread, target_price=100.0)


def shifted(par, bp):
    return apply_shock(par, parallel_shock(bp)).curve


def test_discount_spread_prices_the_pool_at_par(par, pool, mortgage_spread, discount_spread):
    assert pool.price(bootstrap(par), mortgage_spread, discount_spread) == pytest.approx(100.0, abs=1e-9)


def test_average_life_extends_as_rates_rise(par, pool, mortgage_spread):
    wal = {bp: pool.cash_flows(shifted(par, bp), mortgage_spread).wal_years() for bp in (-200, 0, 200)}

    assert wal[200] > wal[0] > wal[-200]


def test_pool_near_current_rates_has_negative_convexity_and_a_similar_treasury_positive(
    par, pool, mortgage_spread, discount_spread
):
    curves = build_risk_curves(par)
    mbs = risk_measures(lambda c: pool.price(c, mortgage_spread, discount_spread), curves)

    # Treasury bullet with the closest effective duration, coupon at the 10y par yield.
    coupon = ten_year_par_yield(curves.base)
    candidates = [FixedRateBond(coupon=coupon, maturity_months=m) for m in range(12, 361, 6)]
    risks = [risk_measures(lambda c, b=b: b.dirty_price(c), curves) for b in candidates]
    treasury = min(risks, key=lambda r: abs(r.eff_duration - mbs.eff_duration))

    assert abs(treasury.eff_duration - mbs.eff_duration) < 0.5
    assert mbs.eff_convexity < 0
    assert treasury.eff_convexity > 0


def test_gain_at_minus_100_is_smaller_than_loss_at_plus_100(par, pool, mortgage_spread, discount_spread):
    base = pool.price(bootstrap(par), mortgage_spread, discount_spread)
    gain = pool.price(shifted(par, -100), mortgage_spread, discount_spread) - base
    loss = base - pool.price(shifted(par, 100), mortgage_spread, discount_spread)

    assert 0 < gain < loss


def test_effective_duration_rises_as_rates_rise_while_prepayments_respond(
    par, pool, mortgage_spread, discount_spread
):
    """From -100 to +50 bp (D-032). Beyond +50 bp CPR is at its floor and the
    pool behaves like a fixed bond; that is documented, not asserted here."""
    durations = []
    for bp in (-100, -50, 0, 50):
        curves = build_risk_curves(apply_shock(par, parallel_shock(bp)).curve.par)
        durations.append(
            risk_measures(lambda c: pool.price(c, mortgage_spread, discount_spread), curves).eff_duration
        )

    assert all(a < b for a, b in zip(durations, durations[1:])), durations
