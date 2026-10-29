from dataclasses import dataclass


@dataclass
class Shape:
    kind: str
    x: int
    y: int
    size: int
