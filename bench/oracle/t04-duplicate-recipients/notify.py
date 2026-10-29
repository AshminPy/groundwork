ONCALL = {"api": "oncall-api@example.com", "web": "oncall-web@example.com", "jobs": "oncall-jobs@example.com"}


def recipients(team: str, extra=None) -> list:
    return [*(extra or []), ONCALL[team]]
