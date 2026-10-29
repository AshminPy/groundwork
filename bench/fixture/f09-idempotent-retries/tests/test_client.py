from payclient.charges import get_charge
from payclient.client import Client


def test_get():
    c = Client(lambda m, u, h, b: (200, {}, {"id": "ch_1"}))
    assert get_charge(c, "ch_1") == {"id": "ch_1"}
