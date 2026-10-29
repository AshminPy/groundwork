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


def test_pod_security_context():
    sc = _deploy()["spec"]["template"]["spec"]["securityContext"]
    assert sc["runAsNonRoot"] is True and sc["runAsUser"] == 10001
    assert sc["seccompProfile"]["type"] == "RuntimeDefault"


def test_every_container():
    for name, c in _containers().items():
        sc = c["securityContext"]
        assert sc["allowPrivilegeEscalation"] is False, name
        assert sc["readOnlyRootFilesystem"] is True, name
        assert [x.upper() for x in sc["capabilities"]["drop"]] == ["ALL"], name


def test_ports_unchanged():
    assert _containers()["orders"]["ports"] == [{"containerPort": 8080}]
