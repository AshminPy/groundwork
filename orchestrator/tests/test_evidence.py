"""Question Evidence Engine (M2): deterministic claim checks, statuses, and the answer workflow around them."""
import subprocess

import pytest

from groundwork_orchestrator import evidence
from groundwork_orchestrator.contract import new_contract
from groundwork_orchestrator.store import new_task_id

CONFIG = 'API_VERSION = "2024-06"\nMAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))\n'
DOC_NEW = "# Reference — API version 2024-06\n\nMaximum page size: 100.\n"
DOC_OLD = "# Reference — API version 2023-01\n\nMaximum page size: 50.\n"


@pytest.fixture
def ws(tmp_path):
    r = tmp_path / "ws"
    (r / "docs").mkdir(parents=True)
    (r / "config.py").write_text(CONFIG)
    (r / "docs" / "api-2024-06.md").write_text(DOC_NEW)
    (r / "docs" / "api-2023-01.md").write_text(DOC_OLD)
    for args in (["init", "-q"], ["add", "."], ["-c", "user.email=t@x", "-c", "user.name=t", "commit", "-qm", "i"]):
        subprocess.run(["git", "-C", str(r), *args], check=True)
    return r


def claim(text, path, start, quote, domain="repo_code", value=None, end=None):
    c = {"text": text, "domain": domain, "refs": [{"path": path, "line_start": start, "line_end": end or start,
                                                   "quote": quote}]}
    return {**c, "value": value} if value else c


PIN = claim("The repository uses API version 2024-06", "config.py", 1, 'API_VERSION = "2024-06"', value="2024-06")


def statuses(found):
    return [(c["status"], c["reason"]) for c in found["claims"]]


def test_located_quote_records_provenance_and_is_not_reviewed(ws):
    found = evidence.assess([claim("Max retries default is 3", "config.py", 2, 'get("MAX_RETRIES", "3")', value="3")],
                            str(ws))
    (c,) = found["claims"]
    assert (c["status"], c["reason"]) == ("UNVERIFIED", "not_reviewed")
    ref = c["refs"][0]
    assert ref["located"] and len(ref["blob_sha"]) == 40 and ref["dirty"] is False and ref["checked_at"]
    assert len(found["repo_commit"]) == 40
    assert evidence.answer_status(found) == "PARTIALLY_SUPPORTED"


@pytest.mark.parametrize("ref,detail", [
    ({"path": "config.py", "line_start": 1, "line_end": 1, "quote": "MAX_RETRIES = int"}, "not in the cited lines"),
    ({"path": "config.py", "line_start": 9, "line_end": 9, "quote": 'API_VERSION = "2024-06"'}, "outside"),
    ({"path": "../outside.py", "line_start": 1, "line_end": 1, "quote": "anything at all"}, "not inside"),
    ({"path": "missing.py", "line_start": 1, "line_end": 1, "quote": "anything at all"}, "not inside"),
    ({"path": "config.py", "line_start": 1, "line_end": 1, "quote": "API"}, "shorter"),
])
def test_quote_must_be_verbatim_at_the_cited_lines(ws, ref, detail):
    found = evidence.assess([{"text": "x", "domain": "repo_code", "refs": [ref]}], str(ws))
    (c,) = found["claims"]
    assert (c["status"], c["reason"]) == ("UNVERIFIED", "not_located") and detail in c["refs"][0]["detail"]
    assert evidence.answer_status(found) == "UNVERIFIED"


def test_whitespace_differences_do_not_break_location(ws):
    found = evidence.assess([claim("pin", "config.py", 1, 'API_VERSION   =\n"2024-06"')], str(ws))
    assert statuses(found) == [("UNVERIFIED", "not_reviewed")]


def test_no_claims_or_no_refs_is_unverified(ws):
    assert evidence.answer_status(evidence.assess([], str(ws))) == "UNVERIFIED"
    found = evidence.assess([{"text": "x", "domain": "other", "refs": []}], str(ws))
    assert statuses(found) == [("UNVERIFIED", "no_refs")]


def test_vendor_doc_for_another_version_is_inapplicable_not_contradicted(ws):
    old = claim("Max page size is 50", "docs/api-2023-01.md", 3, "Maximum page size: 50.", "vendor_doc", value="50")
    found = evidence.assess([PIN, old], str(ws))
    assert statuses(found)[1] == ("UNVERIFIED", "version_mismatch")
    assert found["claims"][1]["status"] != "CONTRADICTED" and evidence.answer_status(found) != "CONTRADICTED"


def test_v_prefixed_version_agreeing_with_the_quote_is_not_contradicted(ws):
    (ws / "version.py").write_text('VERSION = "1.2.3"\n')
    found = evidence.assess([claim("The package version is v1.2.3", "version.py", 1, 'VERSION = "1.2.3"',
                                   value="v1.2.3")], str(ws))
    assert statuses(found) == [("UNVERIFIED", "not_reviewed")]


def test_a_mis_cited_unrelated_number_is_not_a_contradiction(ws):
    found = evidence.assess([claim("The timeout is 30 seconds", "config.py", 2, 'get("MAX_RETRIES", "3")',
                                   value="30")], str(ws))
    assert statuses(found) == [("UNVERIFIED", "value_not_in_quote")]


def test_vendor_value_is_never_contradicted_by_a_code_quote(ws):
    (ws / "client.py").write_text("PAGE = 60\n")
    c = {"text": "Max page size is 500", "domain": "vendor_doc", "value": "500",
         "refs": [{"path": "client.py", "line_start": 1, "line_end": 1, "quote": "PAGE = 60"},
                  {"path": "docs/api-2024-06.md", "line_start": 1, "line_end": 1, "quote": "Reference — API version"}]}
    found = evidence.assess([PIN, c], str(ws))
    assert found["claims"][1]["status"] != "CONTRADICTED"


def test_vendor_doc_for_the_version_in_use_is_accepted(ws):
    new = claim("Max page size is 100", "docs/api-2024-06.md", 3, "Maximum page size: 100.", "vendor_doc", value="100")
    assert statuses(evidence.assess([PIN, new], str(ws)))[1] == ("UNVERIFIED", "not_reviewed")


def test_value_contradicted_by_its_own_located_applicable_quote(ws):
    wrong = claim("Max page size is 500", "docs/api-2024-06.md", 3, "Maximum page size: 100.", "vendor_doc",
                  value="500")
    found = evidence.assess([PIN, wrong], str(ws))
    c = found["claims"][1]
    assert c["status"] == "CONTRADICTED" and c["contradictions"][0]["states"] == "100"
    assert evidence.answer_status(found) == "CONTRADICTED"


def test_value_missing_without_a_single_competing_value_is_unverified_not_contradicted(ws):
    found = evidence.assess([claim("The pin is v9", "config.py", 1, 'API_VERSION = "2024-06"', value="production")],
                            str(ws))
    assert statuses(found) == [("UNVERIFIED", "value_not_in_quote")]


def test_repo_claim_needs_a_code_source_and_vendor_claim_needs_a_doc(ws):
    repo_from_doc = claim("The client uses 100", "docs/api-2024-06.md", 3, "Maximum page size: 100.", "repo_code")
    vendor_from_code = claim("Docs say 2024-06", "config.py", 1, 'API_VERSION = "2024-06"', "vendor_doc")
    assert statuses(evidence.assess([repo_from_doc, vendor_from_code], str(ws))) == [
        ("UNVERIFIED", "missing_required_source"), ("UNVERIFIED", "missing_required_source")]


def test_a_claim_about_what_a_repo_doc_says_needs_a_located_source(ws):
    """repo_doc may cite any located file: docstrings and comments in code are documentation too (the M2 after-run
    showed a true 'the refunds.py docstring says ...' claim being rejected when only .md files counted)."""
    (ws / "CHANGELOG.md").write_text("# Changelog\n- Refunds are validated before they are sent.\n")
    says = claim("The changelog says refunds are validated", "CHANGELOG.md", 2, "Refunds are validated", "repo_doc")
    missing = claim("The changelog says refunds are validated", "CHANGELOG.md", 2, "Refunds are never validated",
                    "repo_doc")
    assert statuses(evidence.assess([says, missing], str(ws))) == [
        ("UNVERIFIED", "not_reviewed"), ("UNVERIFIED", "not_located")]


def test_changed_source_is_stale_until_revalidated_never_contradicted(ws):
    found = evidence.assess([claim("pin", "config.py", 1, 'API_VERSION = "2024-06"', value="2024-06")], str(ws))
    (ws / "config.py").write_text('API_VERSION = "2025-01"\n')
    found = evidence.refresh(found, str(ws))
    assert statuses(found) == [("UNVERIFIED", "stale")]


def test_render_shows_each_status_and_lists_uncertain_claims(ws):
    old = claim("Max page size is 50", "docs/api-2023-01.md", 3, "Maximum page size: 50.", "vendor_doc", value="50")
    text = evidence.render(evidence.assess([PIN, old], str(ws)))
    assert "Evidence: PARTIALLY_SUPPORTED (1 of 2 claims have a located quote" in text
    assert "[unverified: quote located; support not reviewed] The repository uses API version 2024-06" in text
    assert "[unverified: source is for a different API version than the one in use]" in text
    assert "Uncertain: C2 Max page size is 50" in text
    assert "%" not in text


def test_repair_detail_tells_the_worker_what_to_fix(ws):
    found = evidence.assess([claim("x", "config.py", 1, "not in the file")], str(ws))
    detail = evidence.repair_detail(found)
    assert 'C1 "x": quote not found at the cited lines' in detail and "remove the claim" in detail


# ---------------------------------------------------------------- the answer workflow around the engine
def _submit(orch, request, repo):
    return orch.start(new_contract(new_task_id(), request, str(repo), [], False))


GOOD = {"answer": "add() subtracts", "sources": ["app.py:2"], "unknowns": [],
        "claims": [{"text": "add returns a - b", "domain": "repo_code", "value": "a - b",
                    "refs": [{"path": "app.py", "line_start": 2, "line_end": 2, "quote": "return a - b"}]}]}
BAD = {**GOOD, "claims": [{**GOOD["claims"][0], "refs": [{"path": "app.py", "line_start": 1, "line_end": 1,
                                                          "quote": "return a * b"}]}]}


def test_answer_with_located_claims_passes_without_repair(orch, fake, repo):
    fake.plan([{"result": GOOD}])
    st = _submit(orch, "How does the add function work?", repo)
    c = st["contract"]
    assert st["state"] == "PASSED" and c["retry_count"] == 0 and c["answer_evidence"] == "PARTIALLY_SUPPORTED"
    assert c["evidence"]["claims"][0]["refs"][0]["blob_sha"]


def test_unlocated_claim_gets_one_evidence_repair_then_passes(orch, fake, repo):
    fake.plan([{"result": BAD}, {"result": GOOD}])
    st = _submit(orch, "How does the add function work?", repo)
    calls = fake.calls()
    assert st["state"] == "PASSED" and st["contract"]["retry_count"] == 1
    assert "--resume" in calls[-1]["argv"] and "quote not found at the cited lines" in calls[-1]["stdin"]
    assert st["contract"]["answer_evidence"] == "PARTIALLY_SUPPORTED"


def test_claims_still_unsupported_after_the_repair_are_flagged_not_failed(orch, fake, repo):
    fake.plan([{"result": BAD}, {"result": BAD}])
    st = _submit(orch, "How does the add function work?", repo)
    c = st["contract"]
    assert st["state"] == "PASSED" and c["retry_count"] == 1        # one evidence repair, not MAX_REPAIRS
    assert c["answer_evidence"] == "UNVERIFIED" and "not backed by located sources" in c["outcome"]
    assert c["evidence"]["claims"][0]["reason"] == "not_located"


@pytest.mark.parametrize("text,value,quote", [
    ("The request timeout is 30 seconds", "30", "CONNECT_TIMEOUT = 10"),
    ("The cache size is 100", "100", "cache_ttl = 60"),
    ("The server listens on port 8080", "8080", "health_port = 9090"),
    ("The maximum request body size is 5", "5", "MAX_RETRIES = 3  # maximum retries"),
    ("The API version is 2024-06-01", "2024-06-01", 'API = "2024-06"'),
    ("It requires Python 3.11.0", "3.11.0", 'python_requires = ">=3.9.0"'),
])
def test_quotes_about_a_different_setting_or_a_bound_never_contradict(ws, text, value, quote):
    (ws / "s.py").write_text(quote + "\n")
    found = evidence.assess([claim(text, "s.py", 1, quote, value=value)], str(ws))
    assert found["claims"][0]["status"] != "CONTRADICTED", found["claims"][0]


def test_a_claim_that_names_the_other_version_is_about_that_doc_and_is_accepted(ws):
    """Real M2 after-run drafts: 'The older 2023-01 reference says 180 days, but it is not the version the repo uses.'"""
    named = claim("The older 2023-01 doc says the max page size is 50, but that is not the version in use",
                  "docs/api-2023-01.md", 3, "Maximum page size: 50.", "vendor_doc", value="50")
    unnamed = claim("Max page size is 50", "docs/api-2023-01.md", 3, "Maximum page size: 50.", "vendor_doc", value="50")
    assert statuses(evidence.assess([PIN, named, unnamed], str(ws)))[1:] == [
        ("UNVERIFIED", "not_reviewed"), ("UNVERIFIED", "version_mismatch")]


def test_a_repo_doc_claim_may_cite_a_docstring_in_code(ws):
    (ws / "refunds.py").write_text('"""Refund validation, run before create_refund is called."""\n')
    c = claim("The refunds.py docstring says validation runs before create_refund", "refunds.py", 1,
              "Refund validation, run before create_refund is called.", "repo_doc")
    assert statuses(evidence.assess([c], str(ws))) == [("UNVERIFIED", "not_reviewed")]
