import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def test_top():
    assert json.loads((WS / "top_errors.json").read_text()) == [{"path": "/api/pay", "count": 41}, {"path": "/api/search", "count": 27}, {"path": "/api/cart", "count": 19}]
