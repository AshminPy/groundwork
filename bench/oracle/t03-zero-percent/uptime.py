def uptime_pct(up_minutes: int, total_minutes: int) -> float:
    if total_minutes <= 0:
        raise ValueError("total_minutes must be positive")
    return round(up_minutes / total_minutes * 100, 2)
