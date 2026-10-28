import pytest
from flags import env_flag


@pytest.mark.parametrize("raw,want", [("false", False), ("FALSE", False), (" off ", False), ("0", False),
                                      ("no", False), ("true", True), ("Yes", True), ("1", True), ("ON", True)])
def test_values(monkeypatch, raw, want):
    monkeypatch.setenv("NEW_CHECKOUT", raw)
    assert env_flag("NEW_CHECKOUT", default=not want) is want


def test_empty_uses_default(monkeypatch):
    monkeypatch.setenv("NEW_CHECKOUT", "")
    assert env_flag("NEW_CHECKOUT", default=True) is True


def test_invalid(monkeypatch):
    monkeypatch.setenv("NEW_CHECKOUT", "maybe")
    with pytest.raises(ValueError):
        env_flag("NEW_CHECKOUT")
