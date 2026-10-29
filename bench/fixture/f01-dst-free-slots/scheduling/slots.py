from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .intervals import merge

SLOT = timedelta(minutes=30)


def free_slots(busy, day, tz):
    zone = ZoneInfo(tz)
    offset = datetime.combine(day, time(0), zone).utcoffset()
    start = datetime.combine(day, time(9)) - offset
    end = datetime.combine(day, time(17)) - offset
    start, end = start.replace(tzinfo=timezone.utc), end.replace(tzinfo=timezone.utc)
    blocked = merge([(s.astimezone(timezone.utc), e.astimezone(timezone.utc)) for s, e in busy])
    out, t = [], start
    while t + SLOT <= end:
        if not any(s < t + SLOT and t < e for s, e in blocked):
            out.append(t)
        t += SLOT
    return out
