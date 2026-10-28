import os
from dataclasses import dataclass


@dataclass
class Settings:
    base_url: str = "https://api.example.com"
    timeout_s: float = 10.0


def load() -> Settings:
    return Settings(base_url=os.environ.get("APICLIENT_BASE_URL", Settings.base_url),
                    timeout_s=float(os.environ.get("APICLIENT_TIMEOUT", Settings.timeout_s)))
