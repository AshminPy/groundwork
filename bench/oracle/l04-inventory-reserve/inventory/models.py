from dataclasses import dataclass


@dataclass
class Item:
    sku: str
    on_hand: int


@dataclass
class Reservation:
    order_id: str
    sku: str
    qty: int
