"""Focused pilot cases, part 2 (design B8): 1 SRE, 2 infrastructure, 2 long-running. Each names its trap."""
import json
from datetime import datetime, timedelta, timezone

CASES = {}


# ---------------------------------------------------------------------------------------------------------- f06
def _burn_data():
    t0 = datetime(2026, 5, 5, tzinfo=timezone.utc)
    rows = []
    for m in range(480):
        req = 1000
        err = 1 if m % 7 == 0 else 0
        if 120 <= m < 130:
            err = 30            # short sharp spike: 5m window pages, 1h window does not
        if 300 <= m < 360:
            err = 20            # sustained: both page windows
        if 400 <= m < 480:
            err = 9             # slow burn: ticket windows
        rows.append(((t0 + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ"), req, err))
    return rows


def _first(rows, long_w, short_w, threshold):
    for m in range(len(rows)):
        if m + 1 < long_w:
            continue
        def burn(w):
            seg = rows[m - w + 1:m + 1]
            return sum(e for _, _, e in seg) / sum(r for _, r, _ in seg) / 0.001
        if burn(long_w) > threshold and burn(short_w) > threshold:
            return rows[m][0]
    return None


def _firing(rows, long_w, short_w, threshold):
    """Contiguous [first, last] minute ranges during which the alert condition holds."""
    out, cur = [], None
    for m in range(len(rows)):
        on = False
        if m + 1 >= long_w:
            def burn(w):
                seg = rows[m - w + 1:m + 1]
                return sum(e for _, _, e in seg) / sum(r for _, r, _ in seg) / 0.001
            on = burn(long_w) > threshold and burn(short_w) > threshold
        if on and cur is None:
            cur = [rows[m][0], rows[m][0]]
        elif on:
            cur[1] = rows[m][0]
        elif cur is not None:
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out


_BURN = _burn_data()
_ALERTS = {"page_first": _first(_BURN, 60, 5, 14.4), "ticket_first": _first(_BURN, 360, 30, 6)}
_FIRING = {"page": _firing(_BURN, 60, 5, 14.4), "ticket": _firing(_BURN, 360, 30, 6)}
_NAIVE_PAGE = next(r[0] for i, r in enumerate(_BURN) if i >= 4 and sum(e for _, _, e in _BURN[i - 4:i + 1]) / 5000 / 0.001 > 14.4)
assert _ALERTS["page_first"] and _ALERTS["ticket_first"] and _NAIVE_PAGE != _ALERTS["page_first"]

CASES["f06-burn-rate-alerts"] = {
    "category": "sre",
    "trap": "a multi-window alert fires only when both windows exceed the threshold, and only once each window has "
            "full data; a short spike pages on the 5-minute window alone",
    "instruction": """The checkout service has a 99.9% availability SLO, so its error budget is 0.001 of requests.
`metrics/requests.csv` has one row per minute (`minute,requests,errors`, where `minute` is the start of that minute).
We use the multi-window, multi-burn-rate alerts from the Google SRE workbook:
- the burn rate over a window of W minutes ending at minute m is (errors in minutes m-W+1 to m) / (requests in the
  same minutes) / 0.001;
- **page** at minute m when the 60-minute burn rate and the 5-minute burn rate are both above 14.4;
- **ticket** at minute m when the 360-minute burn rate and the 30-minute burn rate are both above 6;
- a window is evaluated only when all of its minutes are in the data (no partial windows).
Write `alerts.json` in the repository root: `{"page_first": ..., "ticket_first": ...}`, each the `minute` value of the
first minute at which that alert fires, or `null` if it never fires. Also write `firing.json`:
`{"page": [[first, last], ...], "ticket": [[first, last], ...]}`, every run of consecutive minutes during which that
alert's condition holds, as the `minute` values of the run's first and last minute, in time order (`[]` if never).""",
    "fixture": {"metrics/requests.csv": "minute,requests,errors\n" + "".join(f"{t},{r},{e}\n" for t, r, e in _BURN),
                "README.md": "# checkout SLO metrics (one row per minute)\n"},
    "oracle": {"alerts.json": json.dumps(_ALERTS, indent=1) + "\n", "firing.json": json.dumps(_FIRING, indent=1) + "\n"},
    "hidden": {"test_alerts_hidden.py": f'''import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def _d():
    return json.loads((WS / "alerts.json").read_text())


def test_page_needs_both_windows():
    assert _d()["page_first"] == {json.dumps(_ALERTS["page_first"])}


def test_page_is_not_the_short_spike():
    assert _d()["page_first"] != {json.dumps(_NAIVE_PAGE)}


def test_ticket_needs_full_six_hour_window():
    assert _d()["ticket_first"] == {json.dumps(_ALERTS["ticket_first"])}


def test_keys():
    assert set(_d()) == {{"page_first", "ticket_first"}}


def test_types():
    d = _d()
    assert all(v is None or isinstance(v, str) for v in d.values())


def test_firing_intervals():
    f = json.loads((WS / "firing.json").read_text())
    assert f == {json.dumps(_FIRING)}
    assert f["page"][0][0] == _d()["page_first"] and f["ticket"][0][0] == _d()["ticket_first"]
'''},
}

# ---------------------------------------------------------------------------------------------------------- f07
_K8S = {
    "k8s/deployment.yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-api
  labels: {app: checkout-api}
spec:
  replicas: 2
  selector:
    matchLabels: {app: checkout}
  template:
    metadata:
      labels: {app: checkout-api, tier: backend}
    spec:
      containers:
        - name: api
          image: registry.example.com/checkout-api:3.4.1
          ports:
            - name: web
              containerPort: 8080
          env:
            - name: DB_POOL_SIZE
              valueFrom:
                configMapKeyRef: {name: checkout-config, key: db_pool}
""",
    "k8s/service.yaml": """apiVersion: v1
kind: Service
metadata:
  name: checkout-api
spec:
  selector: {app: checkout-api, tier: frontend}
  ports:
    - port: 80
      targetPort: http
""",
    "k8s/hpa.yaml": """apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: checkout-api
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: checkout}
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource: {name: cpu, target: {type: Utilization, averageUtilization: 70}}
""",
    "k8s/pdb.yaml": """apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: checkout-api
spec:
  minAvailable: 3
  selector:
    matchLabels: {app: checkout-api}
""",
    "k8s/configmap.yaml": """apiVersion: v1
kind: ConfigMap
metadata:
  name: checkout-config
data:
  db_pool_size: "20"
  log_level: info
""",
}

_K8S_FIXED = {
    "k8s/deployment.yaml": _K8S["k8s/deployment.yaml"].replace("matchLabels: {app: checkout}",
                                                               "matchLabels: {app: checkout-api}")
    .replace("key: db_pool}", "key: db_pool_size}"),
    "k8s/service.yaml": _K8S["k8s/service.yaml"].replace("tier: frontend", "tier: backend").replace(
        "targetPort: http", "targetPort: web"),
    "k8s/hpa.yaml": _K8S["k8s/hpa.yaml"].replace("name: checkout}", "name: checkout-api}"),
    "k8s/pdb.yaml": _K8S["k8s/pdb.yaml"].replace("minAvailable: 3", "maxUnavailable: 1"),
}

CASES["f07-k8s-broken-rollout"] = {
    "category": "infrastructure",
    "trap": "six independent mismatches across four manifests (Deployment selector, Service selector, named "
            "targetPort, HPA target, a PDB that blocks every drain, a wrong ConfigMap key); fixing only the obvious "
            "one leaves the Service without endpoints",
    "instruction": """The `checkout-api` rollout in `k8s/` is broken: the Deployment is rejected, the Service has no
endpoints, the autoscaler does nothing, node drains hang, and the pod would not start if it were scheduled. Fix the
manifests so they are consistent with each other and with these intentions:
- the Deployment is `checkout-api`, with 2 replicas, image `registry.example.com/checkout-api:3.4.1`, and pods
  labelled `app: checkout-api` and `tier: backend`;
- the Service sends port 80 to the container's port 8080;
- the HPA scales the Deployment between 2 and 6 replicas;
- the PodDisruptionBudget allows one pod to be evicted at a time;
- `DB_POOL_SIZE` comes from the ConfigMap's existing pool-size key.
Do not change the image, names, replica counts or the ConfigMap's data. The files must stay valid Kubernetes YAML.
Checked statically; no cluster is used.""",
    "fixture": dict(_K8S),
    "oracle": _K8S_FIXED,
    "hidden": {"test_k8s_hidden.py": '''from pathlib import Path

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
    assert any(tp == p.get("name") or tp == p["containerPort"] for p in cports) and \\
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
'''},
}

# ---------------------------------------------------------------------------------------------------------- f08
_LOG = [
    {"eventSource": "s3", "eventName": "ListBucket", "resource": "arn:aws:s3:::acme-reports"},
    {"eventSource": "s3", "eventName": "GetObject", "resource": "arn:aws:s3:::acme-reports/exports/2026-10-01.csv"},
    {"eventSource": "s3", "eventName": "GetObject", "resource": "arn:aws:s3:::acme-reports/exports/2026-10-02.csv"},
    {"eventSource": "s3", "eventName": "PutObject", "resource": "arn:aws:s3:::acme-reports/exports/summary.json"},
    {"eventSource": "s3", "eventName": "GetObject", "resource": "arn:aws:s3:::acme-reports/private/salaries.csv",
     "errorCode": "AccessDenied"},
    {"eventSource": "s3", "eventName": "DeleteObject", "resource": "arn:aws:s3:::acme-reports/exports/old.csv",
     "errorCode": "AccessDenied"},
    {"eventSource": "sqs", "eventName": "ReceiveMessage", "resource": "arn:aws:sqs:eu-west-1:111122223333:report-jobs"},
    {"eventSource": "sqs", "eventName": "DeleteMessage", "resource": "arn:aws:sqs:eu-west-1:111122223333:report-jobs"},
    {"eventSource": "kms", "eventName": "Decrypt",
     "resource": "arn:aws:kms:eu-west-1:111122223333:key/1234abcd-12ab-34cd-56ef-1234567890ab"},
    {"eventSource": "logs", "eventName": "PutLogEvents",
     "resource": "arn:aws:logs:eu-west-1:111122223333:log-group:/reports/worker:log-stream:i-0abc"},
    {"eventSource": "logs", "eventName": "CreateLogStream",
     "resource": "arn:aws:logs:eu-west-1:111122223333:log-group:/reports/worker:log-stream:i-0def"},
    {"eventSource": "iam", "eventName": "CreateUser", "resource": "arn:aws:iam::111122223333:user/backdoor",
     "errorCode": "AccessDenied"},
]

_POLICY = {"Version": "2012-10-17", "Statement": [
    {"Sid": "ListExports", "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": ["arn:aws:s3:::acme-reports"]},
    {"Sid": "ReadWriteExports", "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"],
     "Resource": ["arn:aws:s3:::acme-reports/exports/*"]},
    {"Sid": "Jobs", "Effect": "Allow", "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage"],
     "Resource": ["arn:aws:sqs:eu-west-1:111122223333:report-jobs"]},
    {"Sid": "Decrypt", "Effect": "Allow", "Action": ["kms:Decrypt"],
     "Resource": ["arn:aws:kms:eu-west-1:111122223333:key/1234abcd-12ab-34cd-56ef-1234567890ab"]},
    {"Sid": "Logs", "Effect": "Allow", "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
     "Resource": ["arn:aws:logs:eu-west-1:111122223333:log-group:/reports/worker:log-stream:*"]},
]}

CASES["f08-iam-least-privilege"] = {
    "category": "infrastructure",
    "trap": "the access log includes denied calls (a probe for a backdoor user, a read outside exports/, a delete) "
            "that must stay denied; ListBucket needs the bucket ARN, object actions the object ARNs",
    "instruction": """`iam/policy.json` is the IAM policy of the reports worker. It allows everything. Replace it with a
least-privilege policy based on `iam/access-log.jsonl`, 30 days of the worker's API calls (one JSON object per line:
`eventSource`, `eventName`, `resource` ARN and, for refused calls, `errorCode`). The IAM action for a line is
`<eventSource>:<eventName>`.
- Allow every call that succeeded in the log, on resources scoped as narrowly as the log supports (a wildcard only
  where the log shows several resources of the same kind under one path, for example several objects under one
  prefix).
- Do not allow anything that the log shows refused, or that is not in the log.
- No `"*"` action, no `<service>:*` action and no `"*"` resource. No `Condition` blocks are needed.
- Keep `"Version": "2012-10-17"`. `iam/main.tf` reads the file with `file()`; do not change it.
Checked statically; no AWS calls.""",
    "fixture": {"iam/policy.json": json.dumps({"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": "*", "Resource": "*"}]}, indent=1) + "\n",
                "iam/access-log.jsonl": "".join(json.dumps(x) + "\n" for x in _LOG),
                "iam/main.tf": '''resource "aws_iam_role_policy" "worker" {
  name   = "reports-worker"
  role   = aws_iam_role.worker.id
  policy = file("${path.module}/policy.json")
}
'''},
    "oracle": {"iam/policy.json": json.dumps(_POLICY, indent=1) + "\n"},
    "hidden": {"test_iam_hidden.py": '''import fnmatch
import json
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def policy():
    return json.loads((WS / "iam" / "policy.json").read_text())


def log():
    return [json.loads(l) for l in (WS / "iam" / "access-log.jsonl").read_text().splitlines() if l.strip()]


def _list(x):
    return x if isinstance(x, list) else [x]


def allowed(action, resource):
    allow = deny = False
    for st in _list(policy()["Statement"]):
        acts = [a.lower() for a in _list(st.get("Action", []))]
        res = _list(st.get("Resource", []))
        hit = any(fnmatch.fnmatchcase(action.lower(), a) for a in acts) and \\
            any(fnmatch.fnmatchcase(resource, r) for r in res)
        if hit and st.get("Effect") == "Deny":
            deny = True
        if hit and st.get("Effect") == "Allow":
            allow = True
    return allow and not deny


def test_every_successful_call_allowed():
    for e in log():
        if "errorCode" not in e:
            assert allowed(f"{e['eventSource']}:{e['eventName']}", e["resource"]), e


def test_refused_calls_stay_refused():
    for e in log():
        if "errorCode" in e:
            assert not allowed(f"{e['eventSource']}:{e['eventName']}", e["resource"]), e


def test_nothing_else():
    for action, resource in [("s3:GetObject", "arn:aws:s3:::other-bucket/exports/x.csv"),
                             ("s3:PutObject", "arn:aws:s3:::acme-reports/private/x"),
                             ("s3:GetObject", "arn:aws:s3:::acme-reports"),
                             ("sqs:SendMessage", "arn:aws:sqs:eu-west-1:111122223333:report-jobs"),
                             ("kms:Encrypt", "arn:aws:kms:eu-west-1:111122223333:key/1234abcd-12ab-34cd-56ef-1234567890ab"),
                             ("logs:DeleteLogGroup", "arn:aws:logs:eu-west-1:111122223333:log-group:/reports/worker"),
                             ("iam:PassRole", "arn:aws:iam::111122223333:role/admin")]:
        assert not allowed(action, resource), (action, resource)


def test_no_wildcards_at_service_level():
    p = policy()
    assert p["Version"] == "2012-10-17"
    for st in _list(p["Statement"]):
        assert "Condition" not in st or st.get("Effect") == "Deny"
        for a in _list(st.get("Action", [])):
            assert a != "*" and not a.endswith(":*"), a
        for r in _list(st.get("Resource", [])):
            assert r != "*" and r != "arn:aws:s3:::*", r


def test_terraform_unchanged():
    assert 'policy = file("${path.module}/policy.json")' in (WS / "iam" / "main.tf").read_text()
'''},
}

# ---------------------------------------------------------------------------------------------------------- f09
_PAY_FIXTURE = {
    "payclient/__init__.py": "",
    "payclient/config.py": '''from dataclasses import dataclass


@dataclass
class Config:
    base_url: str = "https://pay.example.com"
''',
    "payclient/client.py": '''import time
import uuid

from .config import Config


class PaymentError(Exception):
    def __init__(self, status, body=""):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status


class Client:
    """transport(method, url, headers, body) -> (status, headers, body); it may raise ConnectionError."""

    def __init__(self, transport, config=None, sleep=time.sleep, clock=time.time, new_id=lambda: str(uuid.uuid4())):
        self.transport, self.config = transport, config or Config()
        self.sleep, self.clock, self.new_id = sleep, clock, new_id

    def request(self, method, path, headers=None, body=None):
        status, h, b = self.transport(method, self.config.base_url + path, dict(headers or {}), body)
        if status >= 400:
            raise PaymentError(status, b)
        return b
''',
    "payclient/charges.py": '''def create_charge(client, amount_minor: int, currency: str) -> dict:
    return client.request("POST", "/charges", {}, {"amount": amount_minor, "currency": currency})


def get_charge(client, charge_id: str) -> dict:
    return client.request("GET", f"/charges/{charge_id}")
''',
    "tests/test_client.py": '''from payclient.charges import get_charge
from payclient.client import Client


def test_get():
    c = Client(lambda m, u, h, b: (200, {}, {"id": "ch_1"}))
    assert get_charge(c, "ch_1") == {"id": "ch_1"}
''',
}

CASES["f09-idempotent-retries"] = {
    "category": "long-running",
    "trap": "Retry-After can be seconds or an HTTP date; a POST may be retried only with one idempotency key reused "
            "across all its attempts; non-retryable errors must not be retried",
    "instruction": """Add safe retries to the payments client (`payclient/`). The tests in tests/ are incomplete; your
change will also be checked by other tests. Plan the change before you edit, and keep the existing public API.
- `payclient/config.py`: new settings `max_attempts` (total attempts including the first, default 3) and
  `max_backoff` (seconds, default 10.0).
- `payclient/retry.py`: the retry policy. Retry only on HTTP 429, 502, 503, 504, or a `ConnectionError` from the
  transport. Wait before retry n (n = 1, 2, ...) for the response's `Retry-After` header if present, either as
  seconds (`"2"`) or as an HTTP date (`"Wed, 21 Oct 2026 07:28:00 GMT"`, relative to the client's injected `clock()`,
  which returns Unix seconds); otherwise `0.5 * 2 ** (n - 1)` seconds. Never wait more than `max_backoff`, never a
  negative time. Wait with the client's injected `sleep`.
- `Client.request` retries GET, PUT and DELETE, and POST only when the request has an `Idempotency-Key` header.
  When attempts run out, raise `PaymentError` with the last status (for a `ConnectionError`, re-raise it).
  Other 4xx/5xx statuses raise `PaymentError` at once.
- `create_charge` sends an `Idempotency-Key` made with the client's injected `new_id()`: one key per call of
  `create_charge`, the same key on every retry of that call.""",
    "fixture": _PAY_FIXTURE,
    "oracle": {
        "payclient/config.py": '''from dataclasses import dataclass


@dataclass
class Config:
    base_url: str = "https://pay.example.com"
    max_attempts: int = 3
    max_backoff: float = 10.0
''',
        "payclient/retry.py": '''from email.utils import parsedate_to_datetime

RETRY_STATUSES = {429, 502, 503, 504}
SAFE_METHODS = {"GET", "PUT", "DELETE"}


def retryable_request(method: str, headers: dict) -> bool:
    return method.upper() in SAFE_METHODS or (method.upper() == "POST" and bool(headers.get("Idempotency-Key")))


def wait_seconds(n: int, response_headers: dict | None, now: float, max_backoff: float) -> float:
    ra = (response_headers or {}).get("Retry-After")
    wait = None
    if ra is not None:
        ra = str(ra).strip()
        if ra.isdigit():
            wait = float(ra)
        else:
            try:
                wait = parsedate_to_datetime(ra).timestamp() - now
            except (TypeError, ValueError):
                wait = None
    if wait is None:
        wait = 0.5 * 2 ** (n - 1)
    return max(0.0, min(max_backoff, wait))
''',
        "payclient/client.py": '''import time
import uuid

from . import retry
from .config import Config


class PaymentError(Exception):
    def __init__(self, status, body=""):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status


class Client:
    """transport(method, url, headers, body) -> (status, headers, body); it may raise ConnectionError."""

    def __init__(self, transport, config=None, sleep=time.sleep, clock=time.time, new_id=lambda: str(uuid.uuid4())):
        self.transport, self.config = transport, config or Config()
        self.sleep, self.clock, self.new_id = sleep, clock, new_id

    def request(self, method, path, headers=None, body=None):
        headers = dict(headers or {})
        can_retry = retry.retryable_request(method, headers)
        attempts = self.config.max_attempts if can_retry else 1
        for n in range(1, attempts + 1):
            try:
                status, h, b = self.transport(method, self.config.base_url + path, dict(headers), body)
            except ConnectionError:
                if n == attempts:
                    raise
                self.sleep(retry.wait_seconds(n, None, self.clock(), self.config.max_backoff))
                continue
            if status < 400:
                return b
            if status in retry.RETRY_STATUSES and n < attempts:
                self.sleep(retry.wait_seconds(n, h, self.clock(), self.config.max_backoff))
                continue
            raise PaymentError(status, b)
''',
        "payclient/charges.py": '''def create_charge(client, amount_minor: int, currency: str) -> dict:
    headers = {"Idempotency-Key": client.new_id()}
    return client.request("POST", "/charges", headers, {"amount": amount_minor, "currency": currency})


def get_charge(client, charge_id: str) -> dict:
    return client.request("GET", f"/charges/{charge_id}")
''',
    },
    "hidden": {"test_retries_hidden.py": '''import pytest

from payclient.charges import create_charge, get_charge
from payclient.client import Client, PaymentError
from payclient.config import Config


def make(responses, config=None, now=1_800_000_000.0):
    calls, slept, ids = [], [], iter(f"key-{i}" for i in range(100))

    def transport(method, url, headers, body):
        calls.append((method, url, dict(headers)))
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    c = Client(transport, config or Config(), sleep=slept.append, clock=lambda: now, new_id=lambda: next(ids))
    return c, calls, slept


def test_defaults():
    c = Config()
    assert c.max_attempts == 3 and c.max_backoff == 10.0


def test_get_retries_with_backoff_then_succeeds():
    c, calls, slept = make([(503, {}, ""), ConnectionError("x"), (200, {}, {"id": "a"})])
    assert get_charge(c, "a") == {"id": "a"}
    assert len(calls) == 3 and slept == [0.5, 1.0]


def test_retry_after_seconds_and_http_date_and_cap():
    c, calls, slept = make([(429, {"Retry-After": "2"}, ""), (429, {"Retry-After": "Fri, 15 Jan 2027 08:00:04 GMT"}, ""),
                            (200, {}, {})], config=Config(max_attempts=3), now=1_800_000_000.0)
    get_charge(c, "a")
    import email.utils
    target = email.utils.parsedate_to_datetime("Fri, 15 Jan 2027 08:00:04 GMT").timestamp()
    assert target - 1_800_000_000.0 == 4.0
    assert slept[0] == 2.0 and slept[1] == 4.0
    c, calls, slept = make([(503, {"Retry-After": "120"}, ""), (200, {}, {})])
    get_charge(c, "a")
    assert slept == [10.0]


def test_post_uses_one_key_across_retries():
    c, calls, slept = make([(503, {}, ""), (502, {}, ""), (200, {}, {"id": "ch"})])
    assert create_charge(c, 500, "EUR") == {"id": "ch"}
    keys = {h.get("Idempotency-Key") for _, _, h in calls}
    assert len(calls) == 3 and keys == {"key-0"}
    c2, calls2, _ = make([(200, {}, {}), (200, {}, {})])
    create_charge(c2, 1, "EUR")
    create_charge(c2, 2, "EUR")
    assert [h["Idempotency-Key"] for _, _, h in calls2] == ["key-0", "key-1"]


def test_post_without_key_not_retried():
    c, calls, slept = make([(503, {}, "busy")])
    with pytest.raises(PaymentError) as e:
        c.request("POST", "/refunds", {}, {})
    assert e.value.status == 503 and len(calls) == 1 and slept == []


def test_non_retryable_and_exhaustion():
    c, calls, _ = make([(400, {}, "bad")])
    with pytest.raises(PaymentError) as e:
        get_charge(c, "a")
    assert e.value.status == 400 and len(calls) == 1
    c, calls, slept = make([(503, {}, ""), (503, {}, ""), (504, {}, "")])
    with pytest.raises(PaymentError) as e:
        get_charge(c, "a")
    assert e.value.status == 504 and len(calls) == 3 and len(slept) == 2
    c, calls, _ = make([ConnectionError("a"), ConnectionError("b"), ConnectionError("c")])
    with pytest.raises(ConnectionError):
        get_charge(c, "a")
    assert len(calls) == 3
'''},
}

# ---------------------------------------------------------------------------------------------------------- f10
CASES["f10-customer-migration"] = {
    "category": "long-running",
    "trap": "messy real-world data: middle names, phone formats, two date formats, duplicate emails with different "
            "update times, and a re-run on already-migrated data must change nothing",
    "instruction": """Finish the customer-data migration in `migrate/` (`python -m migrate INPUT OUTPUT_DIR`). INPUT is
a JSON-lines file of customer records. Version-1 records have `id`, `name`, `email`, `phone`, `signup` and
`updated_at` (an ISO timestamp). Records that already have `"schema_version": 2` are passed through unchanged, so
running the migration on its own output gives the same output. The tests in tests/ are incomplete; your change will
also be checked by other tests. Plan before you edit.

For each version-1 record, produce `{"schema_version": 2, "id", "given_name", "family_name", "email", "phone",
"signup_date", "updated_at"}`:
- **name:** trim and collapse spaces; `family_name` is the last word and `given_name` the words before it
  (`"Mary Ann  Smith"` gives `"Mary Ann"` and `"Smith"`); a single word is the `given_name`, with an empty
  `family_name`.
- **email:** trimmed and lower-cased. It is invalid unless it has exactly one `@`, a non-empty local part, and a
  domain containing a dot.
- **phone:** E.164. Keep the digits; 10 digits become `+1` and the digits; 11 digits starting with 1 become `+` and
  the digits; an input starting with `+` keeps `+` and its digits if there are 8 to 15 of them. Anything else is
  invalid.
- **signup_date:** `MM/DD/YYYY` or `YYYY-MM-DD` becomes `YYYY-MM-DD`. Anything else, or an impossible date, is
  invalid.
- A record with an invalid field goes to quarantine with the reason of the first failing check, in the order
  `invalid_email`, `invalid_phone`, `invalid_date`.
- Among valid records with the same email, keep the one with the latest `updated_at`; the others go to quarantine
  with the reason `duplicate`.
Write `OUTPUT_DIR/migrated.jsonl` (records sorted by `id`), `OUTPUT_DIR/quarantine.jsonl` (`{"id", "reason"}`,
sorted by `id`) and `OUTPUT_DIR/report.json` (`{"read", "migrated", "quarantined", "by_reason": {...}}`).""",
    "fixture": {
        "migrate/__init__.py": "",
        "migrate/__main__.py": '''import json
import sys
from pathlib import Path

from .transform import transform


def main(argv=None) -> int:
    src, out = (argv or sys.argv[1:])[:2]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in Path(src).read_text().splitlines() if l.strip()]
    migrated = [transform(r) for r in rows]
    (out / "migrated.jsonl").write_text("".join(json.dumps(r) + "\\n" for r in migrated))
    return 0


sys.exit(main())
''',
        "migrate/transform.py": '''def transform(r: dict) -> dict:
    first, last = r["name"].split(" ", 1)
    return {"schema_version": 2, "id": r["id"], "given_name": first, "family_name": last,
            "email": r["email"], "phone": r["phone"], "signup_date": r["signup"], "updated_at": r["updated_at"]}
''',
        "migrate/validate.py": '''"""Field validation for the migration (to be written)."""
''',
        "tests/test_transform.py": '''from migrate.transform import transform


def test_basic():
    r = transform({"id": 1, "name": "Ada Lovelace", "email": "ada@example.com", "phone": "+447700900123",
                   "signup": "2026-01-02", "updated_at": "2026-01-02T00:00:00Z"})
    assert r["given_name"] == "Ada" and r["family_name"] == "Lovelace"
''',
    },
    "oracle": {
        "migrate/validate.py": '''import re
from datetime import date


def email(v: str):
    e = (v or "").strip().lower()
    local, _, domain = e.partition("@")
    if e.count("@") != 1 or not local or "." not in domain:
        return None
    return e


def phone(v: str):
    s = (v or "").strip()
    digits = re.sub(r"\\D", "", s)
    if s.startswith("+"):
        return "+" + digits if 8 <= len(digits) <= 15 else None
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def signup(v: str):
    s = (v or "").strip()
    m = re.fullmatch(r"(\\d{2})/(\\d{2})/(\\d{4})", s) or None
    try:
        if m:
            return date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
        m = re.fullmatch(r"(\\d{4})-(\\d{2})-(\\d{2})", s)
        if m:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None
    return None
''',
        "migrate/transform.py": '''from . import validate


def split_name(name: str):
    words = " ".join((name or "").split()).split(" ")
    if len(words) <= 1:
        return (words[0] if words else ""), ""
    return " ".join(words[:-1]), words[-1]


class InvalidRecord(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def transform(r: dict) -> dict:
    """The version-2 record; raises InvalidRecord with the reason of the first failing check."""
    if r.get("schema_version") == 2:
        return r
    e = validate.email(r.get("email"))
    if e is None:
        raise InvalidRecord("invalid_email")
    p = validate.phone(r.get("phone"))
    if p is None:
        raise InvalidRecord("invalid_phone")
    d = validate.signup(r.get("signup"))
    if d is None:
        raise InvalidRecord("invalid_date")
    given, family = split_name(r.get("name", ""))
    return {"schema_version": 2, "id": r["id"], "given_name": given, "family_name": family, "email": e,
            "phone": p, "signup_date": d, "updated_at": r["updated_at"]}
''',
        "migrate/__main__.py": '''import json
import sys
from collections import Counter
from pathlib import Path

from .transform import InvalidRecord, transform


def main(argv=None) -> int:
    src, out = (argv or sys.argv[1:])[:2]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in Path(src).read_text().splitlines() if l.strip()]
    good, bad = [], []
    for r in rows:
        try:
            good.append(transform(r))
        except InvalidRecord as e:
            bad.append({"id": r.get("id"), "reason": e.reason})
    best = {}
    for rec in good:
        k = rec["email"]
        if k not in best or rec["updated_at"] > best[k]["updated_at"]:
            best[k] = rec
    keep = {id(r) for r in best.values()}
    for rec in good:
        if id(rec) not in keep:
            bad.append({"id": rec["id"], "reason": "duplicate"})
    migrated = sorted(best.values(), key=lambda r: r["id"])
    bad.sort(key=lambda r: r["id"])
    (out / "migrated.jsonl").write_text("".join(json.dumps(r) + "\\n" for r in migrated))
    (out / "quarantine.jsonl").write_text("".join(json.dumps(r) + "\\n" for r in bad))
    report = {"read": len(rows), "migrated": len(migrated), "quarantined": len(bad),
              "by_reason": dict(Counter(r["reason"] for r in bad))}
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\\n")
    return 0


sys.exit(main())
''',
    },
    "hidden": {"test_migration_hidden.py": '''import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
WS = HERE.parent
ROWS = [
    {"id": 1, "name": "  Mary Ann   Smith ", "email": " Mary@Example.COM ", "phone": "(415) 555-0100",
     "signup": "03/09/2024", "updated_at": "2026-01-01T00:00:00Z"},
    {"id": 2, "name": "Cher", "email": "cher@example.org", "phone": "1-212-555-0199", "signup": "2023-12-31",
     "updated_at": "2026-01-01T00:00:00Z"},
    {"id": 3, "name": "Bad Mail", "email": "no-at-sign.example.com", "phone": "4155550100", "signup": "2024-01-01",
     "updated_at": "2026-01-01T00:00:00Z"},
    {"id": 4, "name": "Bad Phone", "email": "bp@example.com", "phone": "555-0100", "signup": "2024-01-01",
     "updated_at": "2026-01-01T00:00:00Z"},
    {"id": 5, "name": "Bad Date", "email": "bd@example.com", "phone": "+44 7700 900123", "signup": "02/30/2024",
     "updated_at": "2026-01-01T00:00:00Z"},
    {"id": 6, "name": "Old Smith", "email": "mary@example.com", "phone": "4155550100", "signup": "2020-01-01",
     "updated_at": "2025-01-01T00:00:00Z"},
    {"id": 7, "name": "Two Errors", "email": "x@", "phone": "1", "signup": "nope", "updated_at": "2026-01-01T00:00:00Z"},
    {"schema_version": 2, "id": 8, "given_name": "Al", "family_name": "Ready", "email": "al@example.com",
     "phone": "+15550000000", "signup_date": "2022-02-02", "updated_at": "2026-01-01T00:00:00Z"},
]


def run(inp, out):
    r = subprocess.run([sys.executable, "-m", "migrate", str(inp), str(out)], cwd=WS, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    rd = lambda n: [json.loads(l) for l in (out / n).read_text().splitlines() if l.strip()]
    return rd("migrated.jsonl"), rd("quarantine.jsonl"), json.loads((out / "report.json").read_text())


def setup_module():
    (HERE / "in.jsonl").write_text("".join(json.dumps(r) + "\\n" for r in ROWS))


def test_records_transformed():
    m, q, rep = run(HERE / "in.jsonl", HERE / "out1")
    by = {r["id"]: r for r in m}
    assert by[1] == {"schema_version": 2, "id": 1, "given_name": "Mary Ann", "family_name": "Smith",
                     "email": "mary@example.com", "phone": "+14155550100", "signup_date": "2024-03-09",
                     "updated_at": "2026-01-01T00:00:00Z"}
    assert by[2]["given_name"] == "Cher" and by[2]["family_name"] == "" and by[2]["phone"] == "+12125550199"
    assert by[8] == ROWS[7]
    assert [r["id"] for r in m] == sorted(r["id"] for r in m)


def test_quarantine_reasons_in_order():
    m, q, rep = run(HERE / "in.jsonl", HERE / "out2")
    assert q == [{"id": 3, "reason": "invalid_email"}, {"id": 4, "reason": "invalid_phone"},
                 {"id": 5, "reason": "invalid_date"}, {"id": 6, "reason": "duplicate"},
                 {"id": 7, "reason": "invalid_email"}]


def test_report():
    m, q, rep = run(HERE / "in.jsonl", HERE / "out3")
    assert rep == {"read": 8, "migrated": 3, "quarantined": 5,
                   "by_reason": {"invalid_email": 2, "invalid_phone": 1, "invalid_date": 1, "duplicate": 1}}


def test_rerun_on_output_is_identical():
    m, q, rep = run(HERE / "in.jsonl", HERE / "out4")
    m2, q2, rep2 = run(HERE / "out4" / "migrated.jsonl", HERE / "out5")
    assert m2 == m and q2 == [] and rep2["migrated"] == len(m)


def test_plus_number_length_bounds():
    rows = [{"id": 10, "name": "A B", "email": "a10@example.com", "phone": "+1234567", "signup": "2024-01-01",
             "updated_at": "z"},
            {"id": 11, "name": "A B", "email": "a11@example.com", "phone": "+123456789012345", "signup": "2024-01-01",
             "updated_at": "z"}]
    (HERE / "in2.jsonl").write_text("".join(json.dumps(r) + "\\n" for r in rows))
    m, q, rep = run(HERE / "in2.jsonl", HERE / "out6")
    assert [r["id"] for r in m] == [11] and q == [{"id": 10, "reason": "invalid_phone"}]
'''},
}
