import json
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
    (HERE / "in.jsonl").write_text("".join(json.dumps(r) + "\n" for r in ROWS))


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
    (HERE / "in2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    m, q, rep = run(HERE / "in2.jsonl", HERE / "out6")
    assert [r["id"] for r in m] == [11] and q == [{"id": 10, "reason": "invalid_phone"}]
