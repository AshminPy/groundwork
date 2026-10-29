from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .intervals import merge

SLOT = timedelta(minutes=30)


def free_slots(busy, day, tz):
    zone = ZoneInfo(tz)
    blocked = merge([(s.astimezone(timezone.utc), e.astimezone(timezone.utc)) for s, e in busy])
    out = []
    for minutes in range(9 * 60, 17 * 60, 30):
        local = datetime.combine(day, time(minutes // 60, minutes % 60), zone)
        t = local.astimezone(timezone.utc)
        end_local = datetime.combine(day, time(17), zone).astimezone(timezone.utc)
        if t + SLOT > end_local:
            continue
        if not any(s < t + SLOT and t < e for s, e in blocked):
            out.append(t)
    return sorted(out)
