`backoff.delays(base, cap, attempts)` should return the list of waits before each retry: retry n
(starting at 0) waits `base * 2**n` seconds, never more than `cap`. Today the first retry already waits `2 * base`,
and the cap is not applied. Fix it. `attempts` of 0 returns an empty list; a negative `base`, `cap` or `attempts`
raises `ValueError`. The tests in tests/ are incomplete; your change will also be checked by other tests. Do not change the public function names or signatures.
