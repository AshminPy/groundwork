Implement `timeparse.parse_duration(text)` in `timeparse.py`. It takes strings such as `"1h30m"`,
`"45s"`, `"2h"`, `"1h 5m 10s"` and returns the total number of seconds as an int. Units are `h`, `m` and `s`, each
at most once, in that order, with optional spaces between parts. Anything else (an empty string, an unknown unit, a
repeated unit, units out of order, a bare number) raises `ValueError`. The tests in tests/ are incomplete; your change will also be checked by other tests. Do not change the public function names or signatures.
