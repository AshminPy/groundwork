import time

from . import config


class Client:
    def __init__(self, transport, settings=None, sleep=time.sleep, clock=time.monotonic):
        self.transport = transport
        self.settings = settings or config.load()
        self.sleep = sleep
        self.clock = clock

    def request(self, method: str, path: str):
        return self.transport(method, self.settings.base_url + path, self.settings.timeout_s)
