from decimal import Decimal

import pytest

from billing.allocate import split


def test_sums_exactly_and_largest_remainder():
    out = split("100.00", [1, 1, 1], "USD")
    assert out == ["33.34", "33.33", "33.33"]
    assert sum(Decimal(x) for x in out) == Decimal("100.00")


def test_ties_go_to_earlier_and_weights_proportional():
    assert split("0.05", [1, 1], "USD") == ["0.03", "0.02"]
    assert split("10.00", [3, 1], "EUR") == ["7.50", "2.50"]


def test_zero_minor_units_and_three():
    assert split("1000", [1, 2], "JPY") == ["333", "667"]
    assert split("1.000", [1, 1, 1], "BHD") == ["0.334", "0.333", "0.333"]


def test_refund_negative():
    out = split("-100.00", [1, 1, 1], "USD")
    assert out == ["-33.34", "-33.33", "-33.33"]


def test_zero_weight_gets_zero():
    out = split("10.00", [0, 1, 2], "USD")
    assert out[0] == "0.00" and sum(Decimal(x) for x in out) == Decimal("10.00")


@pytest.mark.parametrize("args", [("1.00", [], "USD"), ("1.00", [0, 0], "USD"), ("1.00", [1, -1], "USD"),
                                  ("1.00", [1], "XXX")])
def test_errors(args):
    with pytest.raises(ValueError):
        split(*args)


def test_many_shares_sum():
    out = split("0.07", [1] * 10, "USD")
    assert sum(Decimal(x) for x in out) == Decimal("0.07") and out.count("0.01") == 7
