from notify import recipients


def test_extra():
    assert recipients("web", ["boss@example.com"]) == ["boss@example.com", "oncall-web@example.com"]
