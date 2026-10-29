from dataclasses import dataclass


@dataclass
class Config:
    base_url: str = "https://pay.example.com"
