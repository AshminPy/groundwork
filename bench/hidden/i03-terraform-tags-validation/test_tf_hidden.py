import re
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
    for env in ("dev", "staging", "prod"):   # contains([...]) or a regex such as ^(dev|staging|prod)$
        assert re.search(r"\b" + env + r"\b", v.split("validation", 1)[1]), env
    assert re.search(r'error_message\s*=\s*"[^"]+"', v)
