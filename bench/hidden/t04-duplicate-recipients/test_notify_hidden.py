from notify import recipients


def test_calls_independent():
    assert recipients("api") == ["oncall-api@example.com"]
    assert recipients("web") == ["oncall-web@example.com"]
    assert recipients("jobs") == ["oncall-jobs@example.com"]


def test_caller_list_not_modified():
    mine = ["boss@example.com"]
    assert recipients("api", mine) == ["boss@example.com", "oncall-api@example.com"]
    assert mine == ["boss@example.com"]
