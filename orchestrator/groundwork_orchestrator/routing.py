"""Model and effort routing from a policy file. Model names live here and in routing.json, nowhere else.

Tools per role are NOT in the policy: they are a security control and stay in graph.py.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_POLICY = Path(__file__).with_name("routing.json")
REQUIRED_ROLES = ("classifier", "answer", "investigate", "plan", "implement", "implement_complex", "document")


class PolicyError(ValueError):
    pass


def validate_policy(policy: dict) -> None:
    models, efforts, roles = policy.get("models"), policy.get("efforts"), policy.get("roles")
    if not isinstance(models, list) or not isinstance(efforts, list) or not isinstance(roles, dict):
        raise PolicyError("routing policy needs 'models', 'efforts' and 'roles'")
    for name in REQUIRED_ROLES:
        if name not in roles:
            raise PolicyError(f"routing policy has no role {name!r}")
    for name, r in roles.items():
        if not isinstance(r, dict) or r.get("model") not in models:
            raise PolicyError(f"role {name!r}: model {r.get('model') if isinstance(r, dict) else r!r} is not in {models}")
        if r.get("effort") not in efforts:
            raise PolicyError(f"role {name!r}: effort {r.get('effort')!r} is not in {efforts}")


def load_policy(home: Path | None = None) -> dict:
    """The owner's override in <home>/routing.json wins over the packaged default; both are validated."""
    path = Path(home) / "routing.json" if home and (Path(home) / "routing.json").exists() else DEFAULT_POLICY
    try:
        policy = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise PolicyError(f"cannot read routing policy {path}: {e}") from e
    validate_policy(policy)
    policy["_path"] = str(path)
    return policy


def choose(policy: dict, role: str) -> dict:
    r = policy["roles"][role]
    return {"role": role, "model": r["model"], "effort": r["effort"],
            "reason": f"{r.get('reason', '')} (policy {Path(policy['_path']).name})".strip()}


def role_for(workflow: str, risk: str) -> str:
    if workflow == "implement" and risk == "high":
        return "implement_complex"
    return workflow
