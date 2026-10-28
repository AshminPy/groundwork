import re
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
