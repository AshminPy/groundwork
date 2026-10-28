"""Source of the 5 infrastructure cases: Terraform, Kubernetes and Dockerfile edits, checked statically (no cloud or
cluster calls). The Kubernetes checks parse YAML with PyYAML, which the grader's Python must have."""

CASES = {}

_DEPLOY = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders
  labels:
    app: orders
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orders
  template:
    metadata:
      labels:
        app: orders
    spec:
      containers:
        - name: orders
          image: registry.example.com/orders:1.14.2
          ports:
            - containerPort: 8080
        - name: log-shipper
          image: registry.example.com/shipper:0.9.1
"""

_K8S_TEST_HEAD = '''from pathlib import Path

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
'''

CASES["i01-k8s-resources-probes"] = {
    "category": "infrastructure",
    "instruction": """Production readiness review for `k8s/deployment.yaml`. For the `orders` container only, add:
- resource requests of `250m` CPU and `256Mi` memory, and limits of `500m` CPU and `512Mi` memory;
- a readiness probe: HTTP GET `/healthz` on port 8080, initial delay 5 seconds, period 10 seconds;
- a liveness probe: HTTP GET `/livez` on port 8080, initial delay 15 seconds, period 20 seconds.
Leave the `log-shipper` container and everything else unchanged. The file must stay valid Kubernetes YAML.""",
    "fixture": {"k8s/deployment.yaml": _DEPLOY},
    "oracle": {"k8s/deployment.yaml": _DEPLOY.replace("""          ports:
            - containerPort: 8080
""", """          ports:
            - containerPort: 8080
          resources:
            requests: {cpu: 250m, memory: 256Mi}
            limits: {cpu: 500m, memory: 512Mi}
          readinessProbe:
            httpGet: {path: /healthz, port: 8080}
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet: {path: /livez, port: 8080}
            initialDelaySeconds: 15
            periodSeconds: 20
""")},
    "hidden": {"test_k8s_hidden.py": _K8S_TEST_HEAD + '''

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
'''},
}

CASES["i02-k8s-security-context"] = {
    "category": "infrastructure",
    "instruction": """Harden `k8s/deployment.yaml` to meet the restricted Pod Security Standard. Set, at pod level,
`runAsNonRoot: true`, `runAsUser: 10001` and the `RuntimeDefault` seccomp profile. For every container, set
`allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` and drop all Linux capabilities. Do not change
images, names, replicas or ports. The file must stay valid Kubernetes YAML.""",
    "fixture": {"k8s/deployment.yaml": _DEPLOY},
    "oracle": {"k8s/deployment.yaml": _DEPLOY.replace("""    spec:
      containers:
        - name: orders
          image: registry.example.com/orders:1.14.2
          ports:
            - containerPort: 8080
        - name: log-shipper
          image: registry.example.com/shipper:0.9.1
""", """    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: orders
          image: registry.example.com/orders:1.14.2
          ports:
            - containerPort: 8080
          securityContext: &sc
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: [ALL]}
        - name: log-shipper
          image: registry.example.com/shipper:0.9.1
          securityContext: *sc
""")},
    "hidden": {"test_k8s_hidden.py": _K8S_TEST_HEAD + '''

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
'''},
}

_TF = """terraform {
  required_version = ">= 1.6"
}

locals {
  common_tags = {
    owner   = "platform"
    service = "reports"
  }
}

resource "aws_s3_bucket" "reports" {
  bucket = "acme-reports-${var.environment}"
}

resource "aws_sqs_queue" "jobs" {
  name                      = "reports-jobs-${var.environment}"
  message_retention_seconds = 345600
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/reports/worker/${var.environment}"
  retention_in_days = 14
}

variable "environment" {
  type = string
}
"""

_TF_TEST_HEAD = r'''import re
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def _tf():
    return "\n".join(p.read_text() for p in sorted(WS.glob("*.tf")))


def _block(kind, name):
    t = _tf()
    m = re.search(r'resource\s+"' + kind + r'"\s+"' + name + r'"\s*\{', t)
    assert m, (kind, name)
    depth, i = 1, m.end()
    while depth and i < len(t):
        depth += {"{": 1, "}": -1}.get(t[i], 0)
        i += 1
    return t[m.end():i - 1]


def _blocks(kind):
    t = _tf()
    return [n for n in re.findall(r'resource\s+"' + kind + r'"\s+"([^"]+)"', t)]
'''

CASES["i03-terraform-tags-validation"] = {
    "category": "infrastructure",
    "instruction": """In the Terraform in `main.tf`:
1. Every resource must carry tags: `tags = merge(local.common_tags, { environment = var.environment })`.
2. `var.environment` must only accept `dev`, `staging` or `prod`: add a `validation` block with a clear error
   message.
3. Add a `description` to the variable.
Do not rename resources or change their other arguments. No cloud calls: the change is checked statically.""",
    "fixture": {"main.tf": _TF},
    "oracle": {"main.tf": _TF.replace('''  bucket = "acme-reports-${var.environment}"
}''', '''  bucket = "acme-reports-${var.environment}"
  tags   = merge(local.common_tags, { environment = var.environment })
}''').replace('''  message_retention_seconds = 345600
}''', '''  message_retention_seconds = 345600
  tags                      = merge(local.common_tags, { environment = var.environment })
}''').replace('''  retention_in_days = 14
}''', '''  retention_in_days = 14
  tags              = merge(local.common_tags, { environment = var.environment })
}''').replace('''variable "environment" {
  type = string
}''', '''variable "environment" {
  description = "Deployment environment: dev, staging or prod."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of dev, staging or prod."
  }
}''')},
    "hidden": {"test_tf_hidden.py": _TF_TEST_HEAD + r'''
TAGS = re.compile(r'tags\s*=\s*merge\(\s*local\.common_tags\s*,\s*\{\s*environment\s*=\s*var\.environment\s*\}\s*\)')


def test_every_resource_tagged():
    for kind, name in [("aws_s3_bucket", "reports"), ("aws_sqs_queue", "jobs"), ("aws_cloudwatch_log_group", "worker")]:
        assert TAGS.search(_block(kind, name)), (kind, name)


def test_other_arguments_kept():
    assert 'bucket = "acme-reports-${var.environment}"' in re.sub(r"\s+", " ", _block("aws_s3_bucket", "reports"))
    assert re.search(r"message_retention_seconds\s*=\s*345600", _block("aws_sqs_queue", "jobs"))
    assert re.search(r"retention_in_days\s*=\s*14", _block("aws_cloudwatch_log_group", "worker"))


def test_validation():
    t = _tf()
    m = re.search(r'variable\s+"environment"\s*\{(.*?)\n\}', t, re.S)
    assert m
    v = m.group(1)
    assert re.search(r'description\s*=\s*"[^"]+"', v)
    assert re.search(r"validation\s*\{", v)
    for env in ("dev", "staging", "prod"):
        assert f'"{env}"' in v
    assert re.search(r'error_message\s*=\s*"[^"]+"', v)
'''},
}

_S3 = """resource "aws_s3_bucket" "exports" {
  bucket = "acme-customer-exports"
}
"""

CASES["i04-terraform-s3-secure"] = {
    "category": "infrastructure",
    "instruction": """`s3.tf` defines a bucket that holds customer exports. Make it secure, using the AWS provider v5
style (separate resources, not inline blocks on the bucket):
- block all public access (all four settings true);
- enable versioning;
- default encryption with SSE-KMS using the existing key `aws_kms_key.exports` (add that key resource with key
  rotation enabled if it is not defined);
- deny any request that is not over TLS with a bucket policy (`aws:SecureTransport` = false).
Checked statically; no cloud calls.""",
    "fixture": {"s3.tf": _S3},
    "oracle": {"s3.tf": _S3 + '''
resource "aws_kms_key" "exports" {
  description         = "customer exports"
  enable_key_rotation = true
}

resource "aws_s3_bucket_public_access_block" "exports" {
  bucket                  = aws_s3_bucket.exports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "exports" {
  bucket = aws_s3_bucket.exports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "exports" {
  bucket = aws_s3_bucket.exports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.exports.arn
    }
  }
}

data "aws_iam_policy_document" "tls_only" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [aws_s3_bucket.exports.arn, "${aws_s3_bucket.exports.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "exports" {
  bucket = aws_s3_bucket.exports.id
  policy = data.aws_iam_policy_document.tls_only.json
}
'''},
    "hidden": {"test_s3_hidden.py": _TF_TEST_HEAD + r'''

def _one(kind):
    names = _blocks(kind)
    assert len(names) == 1, (kind, names)
    return _block(kind, names[0])


def test_public_access_block():
    b = _one("aws_s3_bucket_public_access_block")
    assert re.search(r"bucket\s*=\s*aws_s3_bucket\.exports\.(id|bucket)", b)
    for k in ("block_public_acls", "block_public_policy", "ignore_public_acls", "restrict_public_buckets"):
        assert re.search(k + r"\s*=\s*true", b), k


def test_versioning():
    b = _one("aws_s3_bucket_versioning")
    assert re.search(r'status\s*=\s*"Enabled"', b)


def test_kms_encryption():
    b = _one("aws_s3_bucket_server_side_encryption_configuration")
    assert re.search(r'sse_algorithm\s*=\s*"aws:kms"', b)
    assert re.search(r"kms_master_key_id\s*=\s*aws_kms_key\.exports\.(arn|id|key_id)", b)
    k = _block("aws_kms_key", "exports")
    assert re.search(r"enable_key_rotation\s*=\s*true", k)


def test_tls_only_policy():
    t = _tf()
    assert _blocks("aws_s3_bucket_policy")
    assert "aws:SecureTransport" in t
    assert re.search(r'"?Deny"?', t)
    assert re.search(r'(values\s*=\s*\[\s*"false"\s*\]|"aws:SecureTransport"\s*[:=]\s*"?false"?)', t)


def test_no_inline_blocks_on_bucket():
    b = _block("aws_s3_bucket", "exports")
    assert not re.search(r"\b(versioning|server_side_encryption_configuration|acl)\b", b)
'''},
}

_DOCKERFILE = """FROM python:latest
ADD https://example.com/tools/healthcheck.sh /usr/local/bin/healthcheck.sh
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
EXPOSE 8000
CMD python -m app
"""

CASES["i05-dockerfile-hardening"] = {
    "category": "infrastructure",
    "instruction": """Harden the `Dockerfile` for production:
- pin the base image to `python:3.12-slim` (no `latest`);
- do not download anything with `ADD <url>`: the repository already contains `scripts/healthcheck.sh`, so copy that
  instead and make it executable;
- install requirements without the pip cache, before copying the rest of the source (for layer caching);
- run as a non-root user named `app` with UID 10001;
- add a `HEALTHCHECK` that runs the health-check script;
- use the exec (JSON array) form for `CMD`.
Keep `EXPOSE 8000` and `WORKDIR /app`. Checked statically; nothing is built.""",
    "fixture": {"Dockerfile": _DOCKERFILE, "requirements.txt": "flask==3.0.3\n",
                "scripts/healthcheck.sh": "#!/bin/sh\nwget -qO- http://127.0.0.1:8000/healthz >/dev/null\n",
                "app/__init__.py": "", "app/__main__.py": "print('app')\n"},
    "oracle": {"Dockerfile": """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY scripts/healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh && useradd --uid 10001 --create-home app
COPY . /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD ["/usr/local/bin/healthcheck.sh"]
CMD ["python", "-m", "app"]
"""},
    "hidden": {"test_dockerfile_hidden.py": r'''import re
from pathlib import Path

WS = Path(__file__).resolve().parent.parent


def _lines():
    out, buf = [], ""
    for raw in (WS / "Dockerfile").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        buf += line[:-1] + " " if line.endswith("\\") else line
        if not line.endswith("\\"):
            out.append(buf)
            buf = ""
    return out


def _ins(name):
    return [l for l in _lines() if l.split(None, 1)[0].upper() == name]


def test_base_pinned():
    assert _ins("FROM") == ["FROM python:3.12-slim"] or [l.split()[1] for l in _ins("FROM")] == ["python:3.12-slim"]


def test_no_remote_add():
    assert not [l for l in _ins("ADD") if re.search(r"https?://", l)]
    assert any("scripts/healthcheck.sh" in l for l in _ins("COPY") + _ins("ADD"))


def test_requirements_before_source():
    lines = _lines()
    pip = next(i for i, l in enumerate(lines) if re.search(r"pip3? install", l))
    assert "--no-cache-dir" in lines[pip] or "PIP_NO_CACHE_DIR" in " ".join(lines)
    full_copy = [i for i, l in enumerate(lines) if re.match(r"COPY\s+(--\S+\s+)*\.\s", l)]
    assert full_copy and pip < full_copy[0]
    req_copy = [i for i, l in enumerate(lines) if l.startswith("COPY") and "requirements.txt" in l]
    assert req_copy and req_copy[0] < pip


def test_non_root_user():
    text = " ".join(_lines())
    assert re.search(r"(useradd|adduser)[^&;]*\b10001\b", text) and re.search(r"\bapp\b", text)
    users = _ins("USER")
    assert users and users[-1].split()[1] in ("app", "10001", "app:app", "10001:10001")


def test_healthcheck_and_exec_cmd():
    assert any("healthcheck.sh" in l for l in _ins("HEALTHCHECK"))
    assert re.match(r'CMD\s+\[\s*"python3?"\s*,\s*"-m"\s*,\s*"app"\s*\]', _ins("CMD")[-1])
    assert any("chmod" in l and "healthcheck.sh" in l for l in _ins("RUN")) or any("--chmod" in l for l in _ins("COPY"))


def test_kept():
    assert "EXPOSE 8000" in _lines() and "WORKDIR /app" in _lines()
'''},
}
