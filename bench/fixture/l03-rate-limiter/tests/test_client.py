from apiclient.client import Client
from apiclient.config import Settings


def test_request():
    calls = []
    c = Client(lambda m, u, t: calls.append((m, u)) or 200, Settings())
    assert c.request("GET", "/x") == 200
    assert calls == [("GET", "https://api.example.com/x")]
