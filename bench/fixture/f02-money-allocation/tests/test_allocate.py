from billing.allocate import split


def test_even():
    assert split("10.00", [1, 1], "USD") == ["5.00", "5.00"]
