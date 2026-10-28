def delays(base: float, cap: float, attempts: int) -> list:
    if base < 0 or cap < 0 or attempts < 0:
        raise ValueError("base, cap and attempts must not be negative")
    return [min(cap, base * 2 ** n) for n in range(attempts)]
