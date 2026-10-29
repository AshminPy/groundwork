from dataclasses import dataclass


@dataclass
class Item:
    sku: str
    on_hand: int
