import time

from . import config
from .ratelimit import TokenBucket


class Client:
    def __init__(self, transport, settings=None, sleep=time.sleep, clock=time.monotonic):
        self.transport = transport
        self.settings = settings or config.load()
        self.sleep = sleep
        self.clock = clock
        self.bucket = TokenBucket(self.settings.rate_per_second, self.settings.burst, clock)

    def request(self, method: str, path: str):
        while not self.bucket.try_acquire():
            self.sleep(self.bucket.wait_time())
        return self.transport(method, self.settings.base_url + path, self.settings.timeout_s)
