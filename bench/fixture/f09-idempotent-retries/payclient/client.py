import time
import uuid

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
        status, h, b = self.transport(method, self.config.base_url + path, dict(headers or {}), body)
        if status >= 400:
            raise PaymentError(status, b)
        return b
