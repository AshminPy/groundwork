import fnmatch
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
        hit = any(fnmatch.fnmatchcase(action.lower(), a) for a in acts) and \
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
