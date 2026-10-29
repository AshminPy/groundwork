from inventory.models import Item
from inventory.service import Inventory


def test_on_hand():
    assert Inventory([Item("a", 3)]).on_hand("a") == 3
