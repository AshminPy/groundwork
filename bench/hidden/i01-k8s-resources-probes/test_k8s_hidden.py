from pathlib import Path

import yaml

WS = Path(__file__).resolve().parent.parent


def _deploy():
    docs = [d for d in yaml.safe_load_all((WS / "k8s" / "deployment.yaml").read_text()) if d]
    dep = [d for d in docs if d.get("kind") == "Deployment"]
    assert len(dep) == 1
    return dep[0]


def _containers():
    return {c["name"]: c for c in _deploy()["spec"]["template"]["spec"]["containers"]}


def test_unchanged_basics():
    d = _deploy()
    assert d["metadata"]["name"] == "orders" and d["spec"]["replicas"] == 3
    assert set(_containers()) == {"orders", "log-shipper"}
    assert _containers()["orders"]["image"] == "registry.example.com/orders:1.14.2"


def test_resources():
    r = _containers()["orders"]["resources"]
    assert r["requests"] == {"cpu": "250m", "memory": "256Mi"}
    assert r["limits"] == {"cpu": "500m", "memory": "512Mi"}


def test_probes():
    c = _containers()["orders"]
    rp, lp = c["readinessProbe"], c["livenessProbe"]
    assert rp["httpGet"]["path"] == "/healthz" and int(rp["httpGet"]["port"]) == 8080
    assert rp["initialDelaySeconds"] == 5 and rp["periodSeconds"] == 10
    assert lp["httpGet"]["path"] == "/livez" and int(lp["httpGet"]["port"]) == 8080
    assert lp["initialDelaySeconds"] == 15 and lp["periodSeconds"] == 20


def test_shipper_untouched():
    assert _containers()["log-shipper"] == {"name": "log-shipper", "image": "registry.example.com/shipper:0.9.1"}
