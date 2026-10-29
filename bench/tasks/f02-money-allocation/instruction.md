`billing.allocate.split(total, weights, currency)` splits an invoice total between cost centres in
proportion to `weights` (non-negative numbers). `total` is a decimal string such as `"100.00"` or `"-50.00"` (a
refund). It must return a list of decimal strings, one per weight, that:
- add up exactly to `total`;
- use the currency's minor units from `billing/currencies.py` (`USD` and `EUR`: 2, `JPY`: 0, `BHD`: 3). Add JPY and
  BHD there; an unknown currency raises `ValueError`;
- are computed by the largest-remainder method on the absolute amount: each share gets the floor of its exact
  proportional amount in minor units, then the leftover minor units go one each to the shares with the largest
  remainders, ties going to the earlier share. A negative total is split as its absolute value and every amount is
  negated;
- give a zero weight exactly zero.
All weights zero, an empty list or a negative weight raise `ValueError`. Amounts are formatted with exactly the
currency's number of decimals (`"0.00"`, `"0"`, `"0.000"`). The tests in tests/ are incomplete; your change will also
be checked by other tests.
