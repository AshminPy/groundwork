# Groundwork assessment and lean redesign proposal

Date 2026-11-09. Status: **proposal for owner review. Nothing is implemented or removed.**
Inputs: `OWNER-REQUIREMENTS.md` (F1–F3, R1–R17), `TRACKER.md` (42 items), `HARNESS-LANDSCAPE.md` (patterns P1–P12),
the repository at `main` `9f551a0`, and existing evidence (research report, Groundwork 3 noise audit, design review,
benchmark calibration).

Labels: **VERIFIED** = read in code or measured; **UNVERIFIED** = not checked; **INFERENCE** = reasoned from verified
facts.

## 0. The one gap that blocks a final decision

**What actually runs on the owner's Mac is UNVERIFIED.** This cloud session has no Groundwork install
(`~/.claude/rules/groundwork/` absent) and no access to the Mac's telemetry. The code tells us what *would* run
(section 1). The telemetry on the Mac records what *did* run: per turn, `observed.tools`, `observed.mcp_servers`,
`observed.agent_types`, `observed.tests_run`, `observed.deployment_performed` and `declared.playbook`
(`hooks/groundwork_telemetry.py:543-573`, VERIFIED). Limitation: it records that the `Skill` tool ran, not which skill.

Read-only audit to run on each Mac (personal and work), about 2 minutes. It prints counts only, no prompt text:

```bash
claude plugin list
ls ~/.claude/rules/groundwork ~/.claude/groundwork/playbooks 2>/dev/null
ls ~/.claude/groundwork/tasks 2>/dev/null | wc -l          # task-ledger records
ls ~/.claude/groundwork/reports 2>/dev/null | tail -3       # dashboard runs
launchctl list | grep -i groundwork                          # scheduled jobs
python3 - <<'EOF'
import json, collections, os
p = os.path.expanduser("~/.claude/groundwork/telemetry/events.jsonl")
tools, mcp, agents, pb = (collections.Counter() for _ in range(4)); n = tests = 0
for line in open(p, encoding="utf-8"):
    try: r = json.loads(line)
    except ValueError: continue
    n += 1; o = r.get("observed", {}); d = r.get("declared", {})
    tools.update(o.get("tools", [])); mcp.update(o.get("mcp_servers", []))
    at = o.get("agent_types", []); agents.update(at if isinstance(at, list) else [at])
    pb[d.get("playbook", "unknown")] += 1; tests += bool(o.get("tests_run"))
print("turns", n, "| turns with tests", tests)
for name, c in (("tools", tools), ("mcp", mcp), ("subagents", agents), ("playbooks", pb)):
    print(name, c.most_common(15))
EOF
```

What the output decides: whether ECC agents (`ecc:*` in subagents) and `/opsx` (OpenSpec skills) are used at all;
whether any playbook other than "unknown" is declared; whether the task ledger has records; whether routines and the
dashboard ever ran. **The recommendations below are provisional until this audit is in.**

## 1. Capability inventory

How each item runs, from the code (VERIFIED unless marked). "Duplicates native" = Claude Code already offers the
same thing.

### Runs automatically in every session

| # | Item | When | Cost (VERIFIED) | Duplicates native? | Value evidence |
|---|---|---|---|---|---|
| 3–7 | 5 rule files | Every turn | 51 KB, about 12.6k tokens | CLAUDE.md / rules are native; content is custom | None measured |
| 1 | ECC plugin | Every turn (descriptions listed) + ECC hooks, `hook_profile=standard` (`install.sh:72`) | 68 agents, 286 skills, 94 commands listed every turn (`claude/groundwork-3-redesign:plugin/toolchain/ecc-inventory.toml:4-5`); calibration tokens 10.6k → 30.5k | Overlaps native subagents and skills | None; Groundwork 3 plan already decided not to enable it |
| 12 | Session snapshot | SessionStart | 1 process | Partly (`--resume`, compaction re-injects rules) | Observed working (`docs/RELEASE-REPORT-2.5.md` §3) |
| 13 | Task brief + decision log | Start, compact, stop | 3 processes | Partly (auto memory UNVERIFIED for this use) | Observed working live (same) |
| 15 | Task intake + authorization gate | Every prompt + every tool call | ~81 ms per tool call (research report §2) | Native permission ask rules (UNVERIFIED in detail, check in Stage 3) | Pilot; no real MATERIAL task completed through it |
| 16 | Task ledger | Used by #15 | 1,004 lines | OpenSpec `tasks.md`, native todo list | Same as #15 |
| 17 | Reply check | Every prompt + stop | Follow-up on 34 of 40 benchmark answers (`docs/RELEASE-REPORT-2.5.md:89`) | No | Negative: adds turns |
| 10 | Push guard | Every Bash call | 1,017 lines | Partly (deny rules); not branch-aware natively | Tested (security fixes F4–F10, CHANGELOG 2.5.0) |
| 11 | Review gate | Stop | 348 lines | Stop hook is native; the check is custom | Heuristic: any reviewer-named call passes (research report §2) |
| 14 | Telemetry | Stop + every tool call | 2 records | OpenTelemetry is native (needs a backend) | Only source of "what ran" data |
| 19 | Deny rules | Always | 10 patterns | Native mechanism | Safety baseline |
| 22 | statusLine | Every render | 867 lines | Native mechanism | UNVERIFIED use; owner's Mac shows another tool's statusLine (release report 2.5 §4) |

### Runs only when triggered or scheduled

| # | Item | Trigger | Value evidence |
|---|---|---|---|
| 8 | 10 playbooks | Model reads one per task (advisory) | Not measured; telemetry `declared.playbook` will show if they are followed |
| 2 | OpenSpec `/opsx` | User or model invokes | Used in this repo's own development (38 change records) |
| 23 | Dashboard | Weekly launchd job by default (`install.sh:113`) | UNVERIFIED that the owner opens it |
| 25 | Routines | Only if scheduled by the owner | 2 recorded runs (research report §2) |
| 26 | Copilot explain | Manual, tmux only | Never trialled on macOS (research report §2) |
| 27–30 | Integrations catalog, capability profiles, update/rollback, routing check | Manual | UNVERIFIED use |
| 31 | Legacy migration | Install | One-time, past |

## 2. Pattern assessment (P1–P12 from `HARNESS-LANDSCAPE.md`)

| # | Pattern | Native / ECC / OpenSpec? | Groundwork today, evidence | Solves | Worth the cost? | Decision |
|---|---|---|---|---|---|---|
| P1 | Tests decide done, not self-report | Native: Stop hook can block; tests are the project's own | Rule text (`evidence-policy.md` §5–6) + ledger + review gate; no measurement | F1, F3, R7 | Yes, if deterministic and cheap | **SIMPLIFY**: one Stop-time completion check that reports the R7 completion state and blocks "done" without a recorded validation command; reuse the reply-check hook's code |
| P2 | Plan before acting | Native plan mode; OpenSpec | Tier rule + OpenSpec for MATERIAL | F2, R5 | Yes, proportional to risk | **KEEP, use native**: plan mode for significant work = the approval point; OpenSpec only for material, multi-session work |
| P3 | Short instruction file | Native CLAUDE.md / rules | Violated: 51 KB every turn | R11 (cost), F1 (clarity) | Removes cost | **IMPLEMENT** by shrinking to one file of about 4 KB |
| P4 | Specs as files | OpenSpec | Used for MATERIAL | F1, R15 | Yes for large work only | **KEEP** for T3; not for T0–T2 |
| P5 | Context hygiene | Native subagents, `/clear`, compaction | Groundwork adds context (rules + ECC listing) | R11 | Removes cost | **IMPLEMENT by removal**: disable ECC by default, shrink rules; Explore subagent for wide searches |
| P6 | Durable progress artifacts | Native todo list, `--resume` | Brief + decision log + snapshot; observed working | R15 | Yes; already built | **KEEP**, merge snapshot and brief into one hook if it cuts code without losing behaviour |
| P7 | Separate reviewer | Native subagents, `/code-review` | Review gate (heuristic), review rules | F3 | Only for high risk; Superpowers' own data shows extra review loops cost ~2x time with no gain | **SIMPLIFY**: independent review for high-risk tiers only, one round by default, must-fix bar stated up front |
| P8 | Small steps, commits, checkpoints | Native checkpoints and rewind, git | Push guard; push-per-green-step proposal (PR #76) | F1, lost work | Yes, native | **KEEP** native; keep push guard |
| P9 | Deterministic enforcement | Native hooks, permission allow/ask/deny | Push guard, deny rules, task gate (custom asks) | F2, R6 | Yes for high-impact actions only | **SIMPLIFY**: replace the custom task gate with native permission **ask** rules for high-impact commands (deploy, apply, IAM, delete, merge); keep deny rules and push guard |
| P10 | Good tool interface | Native tools, MCP, plugins, `/mcp` | Integrations catalog (custom status model) | R13 | Native first | **SIMPLIFY**: native MCP/plugin management; fold "is it working" checks into `groundwork doctor` only where native status is missing (UNVERIFIED gap for CLIs like gcloud, aws) |
| P11 | One writer | Native | Rule text on subagents and Agent Teams | R11 (no duplicate agents) | Yes, one line | **KEEP** as one rule line; drop the Agent Teams option |
| P12 | Start simple, remove parts | — | This review | R16, R17 | — | **IMPLEMENT**: every kept part must pass the benchmark decision rule (section 5) |

## 3. Keep / Simplify / Remove (provisional, pending section 0 audit)

| Decision | Items | Reason (evidence → requirement) |
|---|---|---|
| **KEEP** | #10 push guard, #19 deny rules, #11 review gate (narrowed), #12 snapshot, #13 brief, #14 telemetry (minimal), #2 OpenSpec (material work only), #32–#34 install/uninstall, #29 update/rollback, #39 tests | Deterministic safety (R6), continuity observed working (R15), the only usage evidence (R9), simple rollback (R4) |
| **SIMPLIFY** | #3–#7 rules → one file of about 4 KB; #8 playbooks → keep, trim, read on demand; #17 reply check → completion-state check (R7); #33 `setup.sh` → install, doctor, update, uninstall; #27/#28 integrations and profiles → native MCP/plugins + doctor; #21 CLI → fewer commands; #22 statusLine and #24 usage → keep only if the audit shows use | Always-on cost (P3, R11); completion clarity (F1, R7); native first (R16) |
| **REMOVE** (after audit confirms no use) | #15 task intake/authorization gate, #16 task ledger, #25 routines, #26 copilot, #31 legacy migration, #30 routing check, #20 Agent Teams flag, #9 coach mode (if not wanted; it is opt-in and small) | Pilot with no completed real task; native permission ask rules cover R6; reply-check and gate interruptions conflict with R11; zero or near-zero use |
| **DISABLE by default** | #1 ECC plugin | Largest token cost; overlaps native; Groundwork 3 reached the same decision. Keep a documented opt-in |
| **FREEZE** (no changes until decided separately) | #23 dashboard, #40 Groundwork 3 branch, #42 Architect Coach app | Not on the critical path; G3 heads toward more machinery, which conflicts with R16 |
| **Docs** | #35–#38 | Shrink README to what exists; keep CHANGELOG; archive old release reports and completed OpenSpec changes |

## 4. Proposed lean architecture

The smallest Groundwork that addresses F1–F3 and R1–R17. Native features do the work; Groundwork adds one short
rule file, a few hooks and permission settings.

```
Always loaded (about 4 KB, one file)
  - Work by tier (below), approval triggers, completion states (R7), evidence labels,
    "inspect before concluding", "follow existing patterns", "check versions, compatibility and
    advisories before recommending" (F3), "challenge the owner", report format.

Native Claude Code
  - Plan mode           = the approval point for significant work (F2, R5)
  - Permission rules    = deny (destructive), ask (deploy, apply, IAM, delete, merge, paid), allow (read-only)  (R6)
  - Subagents           = Explore for wide searches, one reviewer for high-risk work; one writer (P11)
  - Checkpoints, resume = rollback and continuity
  - MCP / plugins       = integrations (R13)

Groundwork hooks (deterministic)
  - Push guard           PreToolUse(Bash)
  - Snapshot + brief     SessionStart / PreCompact / Stop   (R15)
  - Completion check     Stop: completion state stated; "done" needs a recorded validation command (R7)
  - Telemetry            Stop: what ran, minimal (R9, R12)

On demand
  - Playbooks (trimmed), OpenSpec for material work

Tooling
  - install / uninstall / update / rollback / doctor
  - "groundwork last": which important capabilities the last task used (R9), from telemetry,
    so replies carry no metadata block
```

Work by tier (one consistent workflow, scaled to risk, R2/R5):

| Tier | Example | Flow |
|---|---|---|
| Question | "How does Flux reconcile Kustomizations?" | Investigate → answer with sources and labels |
| Small change | Bump a label, fix a typo | Change → fast check → report state |
| Standard change | Fix a Helm value, add an alert | Understand → investigate → short plan → implement → validate → report |
| Significant change | New Terraform module, CloudAMQP upgrade, architecture choice | Understand → investigate (incl. versions, compatibility, advisories) → recommend in plan mode → **owner approves** → implement → validate → one independent review → report |
| High-impact action | `terraform apply`, prod deploy, IAM, delete, merge | As significant, plus native permission **ask** at the action, runtime validation, rollback plan |

Report format (short, mobile-readable, R1/R14): result and completion state first; what was wrong and why; evidence;
what changed; how it was proved; what remains. Detail stays in the task brief and decision log, retrievable later.

## 5. Validation strategy

Use the benchmark harness already built on `claude/baseline-benchmark` (V, E, G arms, sandboxed grading, frozen
split, paired statistics; tasks 7.1–7.4 done, runs 6.1 and 7.5 waiting for owner approval).

- **Arms:** V = plain Claude Code; G = Groundwork 2.5 as installed; L = lean Groundwork.
- **Cases:** about 12 synthetic CloudOps tasks in fixtures (no company code; run on the personal Max account):
  Terraform change that must follow existing module conventions; Kustomize/Flux manifest fix; Helm values change;
  incident troubleshooting from logs; a version recommendation with a planted compatibility or security trap (the
  CloudAMQP case); a research question with a checkable answer; a change that **must** stop for approval; a small
  fix that **must not** ask.
- **Metrics (R12):** correctness (hidden tests/key), task completion, serious errors (unsafe action, false "done",
  missed trap), unnecessary interruptions (asks on cases that need none), review iterations, wall time, tokens.
- **Decision rule:** L ships only if it is at least as good as V on correctness and serious errors, better on at
  least one of F1–F3 metrics (false-done claims, missed traps, missing approval), and its token and time cost is
  within an agreed margin of V. A kept component must show it helps, or be a safety control.
- **Limits:** about 12 cases detects only large differences; results are directional. Repeat runs where cheap.

## 6. Implementation plan (staged; each stage is one PR, reviewed and approved before the next)

| Stage | Work | Owner action | Done when |
|---|---|---|---|
| 0 | Run the section 0 audit on both Macs; paste the output | 5 minutes | Inventory "used / unused" columns filled with data |
| 1 | Baseline benchmark: V vs G on the focused cases | Approve plan usage | Report with per-metric differences |
| 2 | Remove confirmed-unused items (section 3 REMOVE), disable ECC by default (documented opt-in); uninstall cleans up; tests updated | Review PR | Suite green; install/uninstall/rollback verified |
| 3 | One rule file of about 4 KB; native permission ask/deny rules for high-impact actions (verify exact settings syntax in docs first) | Review the rule text line by line | Size check passes; permission behaviour checked in a session |
| 4 | Completion check (from the reply-check code), snapshot+brief consolidation, `groundwork last` | Review PR | Hook tests green; live check on the desktop app and from iPhone |
| 5 | Benchmark V vs G vs L; keep or revert each stage by the decision rule | Approve plan usage | Decision recorded in `TRACKER.md` |

Rollback: each stage is a separate release; `groundwork rollback` and git tags restore the previous version.

## 7. Open questions for the owner

1. Run the section 0 audit on both Macs and share the output?
2. Approve the Stage 1 baseline benchmark (plan usage on the personal Max account, synthetic fixtures only)?
3. Keep coach mode (#9) and the Architect Coach app (#42) in scope, or park them?
4. Is the Groundwork 3 branch (#40) paused while we do this?
