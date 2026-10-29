def delays(base: float, cap: float, attempts: int) -> list:
    return [base * 2 ** (n + 1) for n in range(attempts)]
