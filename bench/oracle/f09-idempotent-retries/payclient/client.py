import time
import uuid

from . import retry
from .config import Config


class PaymentError(Exception):
    def __init__(self, status, body=""):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status


class Client:
    """transport(method, url, headers, body) -> (status, headers, body); it may raise ConnectionError."""

    def __init__(self, transport, config=None, sleep=time.sleep, clock=time.time, new_id=lambda: str(uuid.uuid4())):
        self.transport, self.config = transport, config or Config()
        self.sleep, self.clock, self.new_id = sleep, clock, new_id

    def request(self, method, path, headers=None, body=None):
        headers = dict(headers or {})
        can_retry = retry.retryable_request(method, headers)
        attempts = self.config.max_attempts if can_retry else 1
        for n in range(1, attempts + 1):
            try:
                status, h, b = self.transport(method, self.config.base_url + path, dict(headers), body)
            except ConnectionError:
                if n == attempts:
                    raise
                self.sleep(retry.wait_seconds(n, None, self.clock(), self.config.max_backoff))
                continue
            if status < 400:
                return b
            if status in retry.RETRY_STATUSES and n < attempts:
                self.sleep(retry.wait_seconds(n, h, self.clock(), self.config.max_backoff))
                continue
            raise PaymentError(status, b)
