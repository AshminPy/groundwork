import pytest

from inventory import errors
from inventory.models import Item
from inventory.service import Inventory


def inv():
    return Inventory([Item("a", 5), Item("b", 2)])


def test_reserve_and_available():
    i = inv()
    r = i.reserve("a", 3, "o1")
    assert (r.order_id, r.sku, r.qty) == ("o1", "a", 3)
    assert i.available("a") == 2 and i.on_hand("a") == 5


def test_insufficient_and_errors():
    i = inv()
    i.reserve("a", 4, "o1")
    with pytest.raises(errors.InsufficientStock) as e:
        i.reserve("a", 2, "o2")
    assert e.value.available == 1
    with pytest.raises(errors.UnknownSku):
        i.reserve("zz", 1, "o3")
    with pytest.raises(errors.InvalidQuantity):
        i.reserve("a", 0, "o3")
    for name in ("UnknownSku", "InvalidQuantity", "InsufficientStock", "UnknownOrder"):
        assert issubclass(getattr(errors, name), errors.InventoryError)


def test_rereserve_replaces():
    i = inv()
    i.reserve("a", 4, "o1")
    i.reserve("a", 5, "o1")
    assert i.available("a") == 0
    i.reserve("a", 1, "o1")
    assert i.available("a") == 4


def test_release_and_commit():
    i = inv()
    i.reserve("a", 2, "o1")
    i.reserve("b", 2, "o1")
    i.reserve("a", 1, "o2")
    i.release("o2")
    i.release("nope")
    assert i.available("a") == 3
    i.commit("o1")
    assert i.on_hand("a") == 3 and i.on_hand("b") == 0 and i.available("a") == 3
    with pytest.raises(errors.UnknownOrder):
        i.commit("o1")
