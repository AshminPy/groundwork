from .errors import UnknownSku
from .models import Item


class Inventory:
    def __init__(self, items: list):
        self._items = {i.sku: i for i in items}

    def on_hand(self, sku: str) -> int:
        if sku not in self._items:
            raise UnknownSku(sku)
        return self._items[sku].on_hand
