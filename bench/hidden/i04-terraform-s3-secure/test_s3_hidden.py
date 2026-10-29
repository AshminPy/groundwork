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
