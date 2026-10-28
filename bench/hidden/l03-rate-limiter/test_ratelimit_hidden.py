import pytest

from apiclient import config
from apiclient.client import Client
from apiclient.ratelimit import TokenBucket


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_bucket_refill_and_cap():
    c = Clock()
    b = TokenBucket(2, 4, clock=c)
    assert all(b.try_acquire() for _ in range(4))
    assert not b.try_acquire()
    assert b.wait_time() == pytest.approx(0.5)
    c.t += 0.5
    assert b.try_acquire() and not b.try_acquire()
    c.t += 100
    assert b.wait_time(4) == 0
    assert all(b.try_acquire() for _ in range(4)) and not b.try_acquire()


def test_too_many():
    with pytest.raises(ValueError):
        TokenBucket(1, 2, clock=Clock()).try_acquire(3)


def test_config_env(monkeypatch):
    monkeypatch.setenv("APICLIENT_RATE", "3")
    monkeypatch.setenv("APICLIENT_BURST", "7")
    s = config.load()
    assert s.rate_per_second == 3 and s.burst == 7
    monkeypatch.delenv("APICLIENT_RATE")
    monkeypatch.delenv("APICLIENT_BURST")
    s = config.load()
    assert s.rate_per_second == 10 and s.burst == 20


def test_client_sleeps_when_empty():
    clock, slept, calls = Clock(), [], []

    def sleep(s):
        slept.append(s)
        clock.t += s

    s = config.Settings(rate_per_second=1, burst=2)
    cl = Client(lambda m, u, t: calls.append(u) or 200, s, sleep=sleep, clock=clock)
    for _ in range(4):
        assert cl.request("GET", "/a") == 200
    assert len(calls) == 4
    assert sum(slept) == pytest.approx(2.0)
