ONCALL = {"api": "oncall-api@example.com", "web": "oncall-web@example.com", "jobs": "oncall-jobs@example.com"}


def recipients(team: str, extra=[]) -> list:
    extra.append(ONCALL[team])
    return extra
