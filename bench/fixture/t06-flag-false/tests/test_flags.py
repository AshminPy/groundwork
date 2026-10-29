from flags import env_flag


def test_default(monkeypatch):
    monkeypatch.delenv("X_FLAG", raising=False)
    assert env_flag("X_FLAG", True) is True
