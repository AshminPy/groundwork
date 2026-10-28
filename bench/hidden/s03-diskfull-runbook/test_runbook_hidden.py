import re
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
SECTIONS = ["Summary", "Impact", "Diagnosis", "Mitigation", "Escalation"]


def _text():
    return (WS / "RUNBOOK.md").read_text()


def test_sections_in_order():
    heads = [h.strip() for h in re.findall(r"^##\s+(.+)$", _text(), re.M)]
    assert [h for h in heads if h in SECTIONS] == SECTIONS


def _section(name):
    t = _text()
    m = re.search(r"^##\s+" + name + r"\s*$(.*?)(?=^##\s|\Z)", t, re.M | re.S)
    assert m, name
    return m.group(1)


def test_facts():
    t = _text()
    assert "/var/lib/ledger" in t
    assert re.search(r"85\s*%", t) and re.search(r"10\s*(m\b|min)", t)
    assert "/opt/ledger/ops/cleanup.sh" in _section("Mitigation")
    assert "#storage-oncall" in _section("Escalation")
    assert "507" in t and re.search(r"98\s*%", t)


def test_nothing_invented():
    t = _text()
    paths = set(re.findall(r"(/(?:var|opt|etc|srv|data|mnt)/[A-Za-z0-9_./-]+)", t))
    allowed = {"/var/lib/ledger", "/var/lib/ledger/segments", "/opt/ledger/ops/cleanup.sh"}
    assert {p.rstrip(".,)") for p in paths} <= allowed, paths
