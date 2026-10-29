from dataclasses import dataclass


@dataclass
class Config:
    base_url: str = "https://pay.example.com"
    max_attempts: int = 3
    max_backoff: float = 10.0
