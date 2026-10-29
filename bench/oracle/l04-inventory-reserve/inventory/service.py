from .errors import InsufficientStock, InvalidQuantity, UnknownOrder, UnknownSku
from .models import Item, Reservation


class Inventory:
    def __init__(self, items: list):
        self._items = {i.sku: i for i in items}
        self._res = {}   # (order_id, sku) -> Reservation

    def on_hand(self, sku: str) -> int:
        if sku not in self._items:
            raise UnknownSku(sku)
        return self._items[sku].on_hand

    def available(self, sku: str) -> int:
        held = sum(r.qty for (o, s), r in self._res.items() if s == sku)
        return self.on_hand(sku) - held

    def reserve(self, sku: str, qty: int, order_id: str) -> Reservation:
        self.on_hand(sku)
        if qty < 1:
            raise InvalidQuantity(qty)
        prev = self._res.get((order_id, sku))
        avail = self.available(sku) + (prev.qty if prev else 0)
        if qty > avail:
            raise InsufficientStock(sku, qty, avail)
        r = self._res[(order_id, sku)] = Reservation(order_id, sku, qty)
        return r

    def release(self, order_id: str) -> None:
        for k in [k for k in self._res if k[0] == order_id]:
            del self._res[k]

    def commit(self, order_id: str) -> None:
        keys = [k for k in self._res if k[0] == order_id]
        if not keys:
            raise UnknownOrder(order_id)
        for k in keys:
            r = self._res.pop(k)
            self._items[r.sku].on_hand -= r.qty
