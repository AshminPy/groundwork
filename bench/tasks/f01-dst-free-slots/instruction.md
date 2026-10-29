`slots.free_slots(busy, day, tz)` in `scheduling/slots.py` returns the free meeting slots for one
person on one local calendar day. Make it correct:
- The working window is 09:00 to 17:00 local time in `tz` (an IANA name such as `America/New_York`), on `day`
  (a `datetime.date`).
- `busy` is a list of `(start, end)` pairs of timezone-aware datetimes (any zone, any order). Busy intervals may
  overlap or touch, and may extend outside the working window.
- Slots are 30 minutes long, start on the hour or half hour in local time, must lie entirely inside the working
  window, and must not overlap any busy interval (touching is fine).
- Return the slot start times as timezone-aware UTC datetimes, sorted.
- `scheduling/intervals.py` has `merge(intervals)`, which the slot code uses; it must return merged, sorted
  intervals.
The tests in tests/ are incomplete; your change will also be checked by other tests. Keep the function names and
signatures.
