import pytest

from payclient.charges import create_charge, get_charge
from payclient.client import Client, PaymentError
from payclient.config import Config


def make(responses, config=None, now=1_800_000_000.0):
    calls, slept, ids = [], [], iter(f"key-{i}" for i in range(100))

    def transport(method, url, headers, body):
        calls.append((method, url, dict(headers)))
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    c = Client(transport, config or Config(), sleep=slept.append, clock=lambda: now, new_id=lambda: next(ids))
    return c, calls, slept


def test_defaults():
    c = Config()
    assert c.max_attempts == 3 and c.max_backoff == 10.0


def test_get_retries_with_backoff_then_succeeds():
    c, calls, slept = make([(503, {}, ""), ConnectionError("x"), (200, {}, {"id": "a"})])
    assert get_charge(c, "a") == {"id": "a"}
    assert len(calls) == 3 and slept == [0.5, 1.0]


def test_retry_after_seconds_and_http_date_and_cap():
    c, calls, slept = make([(429, {"Retry-After": "2"}, ""), (429, {"Retry-After": "Fri, 15 Jan 2027 08:00:04 GMT"}, ""),
                            (200, {}, {})], config=Config(max_attempts=3), now=1_800_000_000.0)
    get_charge(c, "a")
    import email.utils
    target = email.utils.parsedate_to_datetime("Fri, 15 Jan 2027 08:00:04 GMT").timestamp()
    assert target - 1_800_000_000.0 == 4.0
    assert slept[0] == 2.0 and slept[1] == 4.0
    c, calls, slept = make([(503, {"Retry-After": "120"}, ""), (200, {}, {})])
    get_charge(c, "a")
    assert slept == [10.0]


def test_post_uses_one_key_across_retries():
    c, calls, slept = make([(503, {}, ""), (502, {}, ""), (200, {}, {"id": "ch"})])
    assert create_charge(c, 500, "EUR") == {"id": "ch"}
    keys = {h.get("Idempotency-Key") for _, _, h in calls}
    assert len(calls) == 3 and keys == {"key-0"}
    c2, calls2, _ = make([(200, {}, {}), (200, {}, {})])
    create_charge(c2, 1, "EUR")
    create_charge(c2, 2, "EUR")
    assert [h["Idempotency-Key"] for _, _, h in calls2] == ["key-0", "key-1"]


def test_post_without_key_not_retried():
    c, calls, slept = make([(503, {}, "busy")])
    with pytest.raises(PaymentError) as e:
        c.request("POST", "/refunds", {}, {})
    assert e.value.status == 503 and len(calls) == 1 and slept == []


def test_non_retryable_and_exhaustion():
    c, calls, _ = make([(400, {}, "bad")])
    with pytest.raises(PaymentError) as e:
        get_charge(c, "a")
    assert e.value.status == 400 and len(calls) == 1
    c, calls, slept = make([(503, {}, ""), (503, {}, ""), (504, {}, "")])
    with pytest.raises(PaymentError) as e:
        get_charge(c, "a")
    assert e.value.status == 504 and len(calls) == 3 and len(slept) == 2
    c, calls, _ = make([ConnectionError("a"), ConnectionError("b"), ConnectionError("c")])
    with pytest.raises(ConnectionError):
        get_charge(c, "a")
    assert len(calls) == 3
