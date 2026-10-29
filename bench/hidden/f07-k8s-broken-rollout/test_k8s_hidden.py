from pathlib import Path

import yaml

WS = Path(__file__).resolve().parent.parent


def docs():
    out = {}
    for p in sorted((WS / "k8s").glob("*.y*ml")):
        for d in yaml.safe_load_all(p.read_text()):
            if d:
                out[(d["kind"], d["metadata"]["name"])] = d
    return out


def dep():
    return docs()[("Deployment", "checkout-api")]


def pod_labels():
    return dep()["spec"]["template"]["metadata"]["labels"]


def test_deployment_selector_matches_template():
    sel = dep()["spec"]["selector"]["matchLabels"]
    assert sel and all(pod_labels().get(k) == v for k, v in sel.items())
    assert pod_labels().get("app") == "checkout-api" and pod_labels().get("tier") == "backend"


def test_unchanged_basics():
    d = dep()
    c = d["spec"]["template"]["spec"]["containers"][0]
    assert d["spec"]["replicas"] == 2 and c["image"] == "registry.example.com/checkout-api:3.4.1"
    assert docs()[("ConfigMap", "checkout-config")]["data"] == {"db_pool_size": "20", "log_level": "info"}


def test_service_has_endpoints():
    svc = docs()[("Service", "checkout-api")]["spec"]
    assert all(pod_labels().get(k) == v for k, v in svc["selector"].items())
    port = svc["ports"][0]
    assert port["port"] == 80
    cports = dep()["spec"]["template"]["spec"]["containers"][0]["ports"]
    tp = port.get("targetPort", port["port"])
    assert any(tp == p.get("name") or tp == p["containerPort"] for p in cports) and \
        any((tp == p.get("name") or tp == p["containerPort"]) and p["containerPort"] == 8080 for p in cports)


def test_hpa_targets_the_deployment():
    h = docs()[("HorizontalPodAutoscaler", "checkout-api")]["spec"]
    assert h["scaleTargetRef"]["kind"] == "Deployment" and h["scaleTargetRef"]["name"] == "checkout-api"
    assert h["minReplicas"] == 2 and h["maxReplicas"] == 6


def test_pdb_allows_one_eviction():
    p = docs()[("PodDisruptionBudget", "checkout-api")]["spec"]
    assert all(pod_labels().get(k) == v for k, v in p["selector"]["matchLabels"].items())
    replicas = dep()["spec"]["replicas"]
    if "maxUnavailable" in p:
        assert p["maxUnavailable"] in (1, "1", "50%")
    else:
        assert int(p["minAvailable"]) == replicas - 1


def test_configmap_key_exists():
    env = dep()["spec"]["template"]["spec"]["containers"][0]["env"]
    ref = next(e for e in env if e["name"] == "DB_POOL_SIZE")["valueFrom"]["configMapKeyRef"]
    cm = docs()[("ConfigMap", ref["name"])]
    assert ref["key"] == "db_pool_size" and ref["key"] in cm["data"]
