from __future__ import annotations

import datetime as dt

from src.metrics import Rate, compute_conversion_rates, compute_funnel, rate
from src.sales_cycle import average_and_median, days_between


def test_days_between_handles_missing_dates():
    assert days_between(None, dt.datetime(2026, 1, 1)) is None
    assert days_between(dt.datetime(2026, 1, 1), None) is None


def test_days_between_computes_correctly():
    start = dt.datetime(2026, 1, 1)
    end = dt.datetime(2026, 1, 15)
    assert days_between(start, end) == 14


def test_average_and_median_ignore_none_and_handle_empty():
    avg, med, n = average_and_median([1, 3, None, 5])
    assert n == 3
    assert avg == 3.0
    assert med == 3.0

    avg2, med2, n2 = average_and_median([])
    assert (avg2, med2, n2) == (None, None, 0)


def test_median_is_not_distorted_by_one_long_outlier():
    # 3 short cycles + 1 very long one — median should stay near the cluster,
    # average should be pulled up, exactly the reason both are tracked.
    avg, med, n = average_and_median([5, 6, 7, 200])
    assert med == 6.5
    assert avg == 54.5


def test_rate_zero_denominator_returns_none_percentage_not_a_crash():
    r = rate(0, 0)
    assert r.percentage is None
    assert "n/a" in r.display


def test_rate_numerator_and_denominator_shown_in_display():
    r = rate(2, 8)
    assert r.numerator == 2
    assert r.denominator == 8
    assert r.percentage == 25.0
    assert r.display == "2 of 8 — 25.0%"


def test_funnel_and_conversion_rates_run_on_empty_database(session):
    funnel = compute_funnel(session)
    assert funnel.researched_accounts == 0
    rates = compute_conversion_rates(funnel)
    # Every rate on an empty DB must be a safe "n/a", never a crash or a lie.
    assert rates.research_to_access.percentage is None
    assert rates.win.percentage is None
