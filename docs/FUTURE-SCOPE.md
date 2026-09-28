# Future scope — the agreed direction for Groundwork and the wider Claude harness

**Status of this document:** design intent, agreed 2026-09-20. It changes nothing at runtime. Every item below is labelled either **CURRENT (1.1.0)** — implemented, installed, and covered by [VALIDATION.md](VALIDATION.md) — or **FUTURE** — a direction to evaluate, not a capability that exists. Nothing marked FUTURE should be described anywhere as working.

## 1. The goal

Build a Claude harness that consistently produces the best practical result for the task with minimal babysitting: high-quality results, evidence-backed reasoning, explicit uncertainty when something is not verified, current best practice, strong architecture and design thinking, security, reliability, maintainability, operational excellence, sensible scalability, cost and context efficiency, real testing and validation, truthful success/failure reporting, and autonomous execution whenever the correct next step is clear.

The harness must avoid both failure modes:

- **under-engineering** — a first implementation that solves the first case and makes normal evolution hard (the first cluster wired straight into code; a second cluster needs a redesign; switching the LLM provider needs invasive changes; manual operational steps that should have been configuration; tests that pass while the real integration path was never exercised);
- **over-engineering** — abstractions, ceremony, frameworks and process nobody asked for.

Governing principle, unchanged from `rules/architecture-quality.md`:

> Use the smallest sound approach that satisfies today's requirement while preserving clear, low-cost paths for reasonably foreseeable future change.

When it is material to the task, Claude should answer internally: what is likely to change; what should be configuration rather than code; what needs a stable interface; how a second instance, provider or environment would be added; what can fail; how it is observed and troubleshot; how it is secured; how it is tested; how it is deployed and rolled back; what the scaling and cost implications are. **CURRENT (1.1.0):** exactly these questions are in `rules/architecture-quality.md` §2 and are required before MATERIAL work; for TRIVIAL and STANDARD work only the dimensions that apply are considered.

## 2. Two conceptual layers — not one giant framework

Groundwork must not become a general-purpose framework, and it must not become the home of every personal, fitness, writing or presentation rule.

### 2.1 Universal core — small, always relevant

Applies across many task types and therefore must stay small enough not to pollute every context:

- evidence-backed reasoning and explicit uncertainty
- safe autonomy (continue when the next step is clear; stop only for genuine owner decisions)
- destructive-action safety
- prompt-injection and untrusted-content discipline
- context hygiene
- a concise communication / output contract
- truthful completion and status reporting

**CURRENT (1.1.0):** these live partly in Groundwork (`evidence-policy.md` §1–2 labels and evidence priority; `engineering-workflow.md` §4 autonomy; the push guard; the snapshot's data-boundary framing) and partly in the user's own rules (`behavior.md` reply format and plain language, `security.md`). They are not yet separated into an explicit "core" file set.
**FUTURE:** evaluate extracting the universal items into one deliberately small always-loaded layer, so that domain layers (including Groundwork) can be scoped and loaded only when relevant. Do this only if measurement shows the always-loaded context is a real cost or that domain rules leak into unrelated tasks.

### 2.2 Domain capabilities — loaded only when relevant

| Domain | Capabilities (examples) | CURRENT (1.1.0) | FUTURE |
|---|---|---|---|
| Engineering | Groundwork, ECC, OpenSpec, engineering review and validation | Groundwork rules are user-level (always loaded); ECC agents/skills load on demand; OpenSpec per repo | Consider scoping Groundwork's engineering rules so they load only for engineering work (path-scoped rules or a skill), keeping the universal core global |
| Cloud / IaC | AWS, GCP, Kubernetes, Terraform review | `rules/cloud.md` is already path-scoped (`paths:` frontmatter); domain reviewer agents exist in `~/.claude/agents/` | Domain packs as scoped rules / skills, added when a real task needs them |
| Research / troubleshooting | evidence-first research and diagnostics | `rules/troubleshooting.md` (user rule); `evidence-policy.md` §7 RCA rule | Scoped diagnostic workflow, not a global rule |
| Documentation | documentation workflow | user skills (readme-writer, runbook-writer, adr-writer, …) | unchanged; keep as skills |
| Presentations | presentation workflow | user skills (presentation-builder, demoprep) | unchanged; keep as skills |
| Fitness / personal | domain evidence and safety guidance | auto-memory notes only | never inside Groundwork; a scoped skill or memory if needed |
| Data analysis | analysis workflow and tooling | none | add only when a real task exposes the gap |

Prefer on-demand skills, path-scoped rules, and native Claude mechanisms over large globally loaded prompts.

## 3. Groundwork's role

Groundwork stays the engineering-quality and governance layer: understanding a project before changing it; TRIVIAL / STANDARD / MATERIAL routing; evidence-backed engineering decisions; architecture and design quality; security, reliability and operability considerations; the implementation workflow; independent review; testing and runtime validation; continuation of existing engineering projects; truthful COMPLETE / PARTIAL / BLOCKED / PLANNED / FAILED status.

**CURRENT (1.1.0):** all of the above are implemented — three rules and three hooks, see [ARCHITECTURE.md](ARCHITECTURE.md). Independent review and protected-branch safety are deterministic hooks; the rest is rule text.

**FUTURE:** keep the surface this size. New Groundwork behaviour is added only under the validation-driven rule in §10.

## 4. OpenSpec and ECC

- **OpenSpec = WHAT / WHY / acceptance criteria. Groundwork = HOW engineering work is executed, governed and proven.** Use OpenSpec proportionally: always for MATERIAL changes, for STANDARD changes only when behaviour is externally observable, never for TRIVIAL work. **CURRENT (1.1.0):** this is `engineering-workflow.md` §1–2.
- **ECC is the specialist engineering toolbox.** Groundwork uses ECC agents and skills when they materially help and never duplicates them. **CURRENT (1.1.0):** Groundwork ships no agents or skills of its own; reviewers, planners and explorers are ECC's or the user's.

## 5. Execution model

Choose the simplest useful model automatically: **main session** for straightforward or mostly sequential work; a **subagent** for focused, isolated investigation, research, testing or review; an **Agent Team** only when genuinely independent collaborative workstreams exist and team communication materially improves the result. The user never specifies how many agents, which roles, or which technology specialist. Roles are derived from the task. No permanent agent zoo.

**CURRENT (1.1.0):** `engineering-workflow.md` §6 encodes exactly this, including the fallback to subagents when teams are disabled or the session is non-interactive; the review gate recognises reviewer teammates. Agent Teams are opt-in (`./install.sh --agent-teams`) and have not been exercised live on this machine.
**FUTURE:** observe real team use in pilots before adding any team-specific hook (for example `TeammateIdle`/`TaskCompleted` quality gates). Not built now.

## 6. Context engineering

Long sessions degrade. The aim is not to preserve every token; it is **fresh reasoning + durable verified state + current repository/runtime evidence**, rather than one indefinitely growing conversation.

**CURRENT (1.1.0):** the SessionStart snapshot gives every session deterministic repository facts; `engineering-workflow.md` §6–7 already direct large exploration, log reading and reviews into subagents and tell Claude to treat memory and session files as hints to verify.
**FUTURE (evaluate, do not build yet):** keep the orchestrator context focused; delegate large repository exploration, logs, research and reviews into isolated contexts as a default rather than a suggestion; use Claude's native project memory deliberately; rely on Git/code/tests/runtime as the authoritative project state; make fresh-session reconstruction the normal path instead of repeated lossy compaction. **No custom vector database, memory daemon or persistence framework** unless real testing proves native mechanisms insufficient.

## 7. Cross-session continuity

A future session continues an existing project without the old chat, using in order: current repository/runtime evidence → Git state and history → OpenSpec/task artifacts → project documentation → tests → Claude native memory → minimal continuation information only if genuinely needed. Stale memory never overrides current repository or runtime evidence. Old Agent Team processes need not survive a session; a fresh session reconstructs state and spawns new agents if needed.

**CURRENT (1.1.0):** `engineering-workflow.md` §7 and the snapshot hook implement this order.
**CURRENT (2.0):** the minimal continuation record described below as FUTURE has been built, for the narrow case it names — non-OpenSpec-tracked work only. `hooks/groundwork_session_snapshot.py`'s `investigation_path()`/`investigation_facts()` surface one small, capped, per-repository Markdown file (objective, proven facts, evidence, decisions, active/rejected hypotheses with reason, files changed, validation results, blockers, uncertainty, remaining tasks, next action — never chain-of-thought) at SessionStart, when one exists; `engineering-workflow.md` §7 states the writing/reopening rules. It is not a database or daemon, is not installed or managed by `install.sh` (created lazily by the model's own write, like `telemetry/`/`reports/`), and current repository/runtime evidence still always outranks it. OpenSpec-tracked work still has no separate Groundwork state file — task checklists and git remain the record there.
**FUTURE (superseded by the above for the case it named):** ~~add a minimal continuation record only if a pilot shows reconstruction from the repository losing something material~~ — done in 2.0, see above.

## 8. Response style

Universal principles: answer or verdict first; simple, clear English; minimum necessary detail; evidence where relevant; uncertainty stated plainly; one best next action when useful. The domain then sets the format:

| Domain | Shape |
|---|---|
| Engineering | issue → evidence → decision → validation → next action, ending in the completion block |
| Troubleshooting | symptom → evidence → likely cause → test → fix |
| Fitness | recommendation → evidence strength → safety considerations |
| Presentation / documentation / email | the finished artifact |

Engineering status blocks are never forced onto unrelated personal tasks. **CURRENT (1.1.0):** the completion block is mandatory for STANDARD/MATERIAL engineering tasks only (`engineering-workflow.md` §3); the universal principles live in the user's `behavior.md`/`response-contract.md`. **FUTURE:** if the universal core in §2.1 is extracted, the communication principles move there and the domain shapes stay with their domains.

## 9. MCP and external tools

MCP servers are optional capabilities, never mandatory Groundwork dependencies. Likely future needs: GitHub, AWS, GCP, Kubernetes, browser/Playwright, trusted documentation and search, other APIs. Principles: add or use only for a real workflow need; prefer official or highly trusted implementations; least privilege; no unnecessary credentials; retrieved content is untrusted data; account for prompt-injection and tool-action risk; do not install every MCP globally. The harness discovers what is available and uses only what the task needs.

**CURRENT (1.1.0):** Groundwork requires no MCP server and configures none. **FUTURE:** an approved-MCP list may be versioned (see §11) once specific servers earn their place through real tasks.

## 10. Safety

Future safety work covers more than Git: destructive shell commands; destructive Git operations; cloud and IAM changes; production deployments; deleting or modifying data; weakening security controls; prompt injection from repositories, websites, MCP responses, documents, logs, issues and external APIs. Untrusted retrieved content is **data, not authority**; instructions embedded in it never override the user's request, trusted system instructions, or Groundwork's safety rules. Where possible, hard boundaries use deterministic permissions and hooks rather than prompt text.

**CURRENT (2.0):** deterministic — the protected-branch/force-push guard, the review gate, `permissions.deny` for secret paths and destructive shell commands, auto-mode `soft_deny` for infra mutations, ECC's GateGuard and `--no-verify` block; the snapshot frames repository text as data with per-field caps. Advisory — `evidence-policy.md`, `security.md`, and the workflow rule's "never default to `--dangerously-skip-permissions`", now explicit for builder-role work too (`engineering-workflow.md` §6's persona section, §F.5): read-only discovery is safe by default, mutating operations require the existing §4 authorization rule.

**DEFERRED at Groundwork 2.0 (owner decision, 2026-09-28) — three named Tier-2 candidates, evaluated and explicitly not built:** `openspec/changes/groundwork-2-enterprise-sre/design.md` §M/D5 designed a tiered menu adding deterministic guards for production Terraform applies, production-namespace `kubectl` mutations, and IAM-mutating cloud CLI commands, structurally mirroring the existing push guard. The owner declined to build any of the three for this release: *"production-vs-nonprod detection depending on heuristic naming risks false confidence"* — a guard that infers "is this production" from naming convention alone is exactly the kind of advisory-strength mechanism this section's own validation-driven rule (§12) warns against overbuilding on inference rather than evidence. This satisfies §12's own bar in the negative direction: candidate 2 (native Claude Code/Groundwork/ECC/OpenSpec cannot already solve it) is true, but no evidence yet shows a *portable, non-heuristic* way to identify a production target across arbitrary repositories, so criterion 3 (materially improves safety without a false-confidence cost) is not yet met. **FUTURE (evaluate):** the same three candidates remain live options if a real incident or task exposes the gap concretely, or if a deterministic, non-heuristic, provably-portable production-target-identification mechanism is found (e.g. a required, machine-readable per-environment declaration the repository itself commits to, rather than inferred naming) — see `design.md` §M/D5 for the full tiered design, kept as the reference point rather than re-designed from scratch when revisited. The known parser limits of the push guard (wrappers other than `sh/bash/zsh -c` and `eval`, non-exact branch names) stay documented until evidence justifies more.

## 11. Versioning and reproducibility

Long term, the effective harness is reproducible and version-controlled: the global `CLAUDE.md`, user rules, the Groundwork version, custom agents, custom skills, hooks and settings entries, approved MCP definitions, and the response contract. Never versioned: secrets, credentials, tokens, private runtime data. The goal is to rebuild the intended setup cleanly on another machine.

**CURRENT (1.1.0):** Groundwork itself is versioned and reinstallable (`install.sh`, additive settings merge, CHANGELOG); the user's rules, agents and skills are mirrored from a separate personal toolkit repository whose installer now excludes Groundwork's files. **FUTURE:** one reproducible definition of the whole effective harness (which rules, which agents/skills, which settings keys, which MCPs), with the toolkit and Groundwork installers composing rather than overlapping.

## 12. Validation-driven evolution

Nothing is added because it sounds useful. A mechanism is added only when all four hold:

1. a real task exposed a gap;
2. native Claude Code, Groundwork, ECC or OpenSpec cannot already solve it adequately;
3. the new mechanism materially improves quality, safety, reliability or autonomy;
4. the benefit justifies the complexity and context cost.

The **SRE Agent pilot** is the first major real-world validation of Groundwork 1.1.0. Its evidence decides what Groundwork needs next. Until then, every FUTURE item in this document is a candidate, not a plan of record.

## 13. Curated skills and routine candidates (Groundwork 2.1, evaluated 2026-09-28)

Researched live against current sources, not adopted automatically — "third-party skills must not become mandatory Groundwork dependencies," per explicit instruction.

**Skills:**
- **`wshobson/agents`** (40K★, MIT, weekly commits) — a native Claude Code plugin marketplace with materially deeper SRE/CloudOps skill coverage than ECC (dedicated cloud-infrastructure, kubernetes-operations, incident-response, CI/CD, observability plugins, each individually installable). Identified during the 2.1 dependency audit. **Remains a documented candidate only, not adopted** — third-party trust surface unaudited, per explicit owner instruction not to auto-adopt.
- **`mattpocock/skills`' `teach` skill** (MIT, actively maintained) — a genuine teaching-technique skill (persistent multi-session workspace: mission/resources/lessons/learning-records; implements retrieval practice, spacing, interleaving), and it ships `disable-model-invocation: true` — already lazy, user-invoked-only (`/teach`) by its own design. **Recommended as an optional install** for anyone who wants deeper teaching technique than `playbooks/explain.md`'s own evidence-grounded teaching branch (Groundwork 2.0) provides; not installed by Groundwork, EXPLAIN's routing/evidence ownership is unchanged.
- **Task Observer** (canonical: `rebelytics/one-skill-to-rule-them-all`, CC BY 4.0, active) — real, but its own install instructions ask for a CLAUDE.md directive invoking it "at the start of any task-oriented session" because description-matching alone under-triggers it, i.e. it's designed near-always-on with standing file-write side effects — the opposite of Groundwork's context-frugality principle. Combined with Groundwork's own telemetry schema not capturing the sequence/timing detail a reliable pattern-miner needs (it records tool/agent/validation *classes*, not sequences), a safe Groundwork-native implementation would need a telemetry-schema change with its own privacy review first. **Deferred**, not built speculatively; the telemetry extension it would need is the actual future candidate, not the observer itself.
- Security-review, architecture-review, documentation-generation, and diagram/presentation capability all already exist as official or well-established options (Anthropic's `/security-review`, official `code-review`/`feature-dev` plugins, official PPTX skill) — no gap for Groundwork to fill here.

**Routine candidates evaluated, not built in 2.1** (scored against VALUE / RELIABILITY / EVIDENCE QUALITY / AUTOMATION SAFETY / EXTERNAL ACCESS / NOISE RISK / MAINTENANCE COST — six other routines shipped in 2.1: Jira EOD, daily tech news, weekly status, PR/review follow-up, daily work/TODO digest, documentation drift):
- **Certificate/PKI expiry awareness** — high value, but needs a configured certificate inventory source Groundwork doesn't have by default; candidate once a concrete evidence source is named.
- **Dependency/security advisory digest** — high value, moderate reliability (advisory feeds vary in quality/noise per ecosystem); candidate, needs a curated source list first.
- **Infrastructure drift detection** — high value for IaC-heavy environments, but needs `terraform plan`-equivalent evidence run somewhere Groundwork can read; overlaps with what a real CI pipeline should already be doing.
- **Cost anomaly review** — needs a configured cloud billing/cost-explorer access Groundwork doesn't assume exists.
- **Stale RCA follow-up** — plausible extension of the existing troubleshoot/investigation-continuity mechanism; a real candidate for a future pass once the six shipped routines have real-world evidence behind them.
- **Release readiness** — overlaps significantly with the existing completion-facts model (`engineering-workflow.md` §3) and the weekly-status routine; likely folds into that rather than becoming a seventh separate routine.

None of these were marked high-priority in the 2.1 brief; building all of them untested against real external accounts (this implementation environment has none) would be exactly the overbuilding Groundwork's own principles warn against. Revisit after the six shipped routines have real usage evidence.

## 14. Summary table

| Area | CURRENT (1.1.0) | FUTURE / PLANNED DIRECTION |
|---|---|---|
| Design-quality questions | in `architecture-quality.md`, required for MATERIAL | unchanged |
| Universal core vs domain layers | mixed across Groundwork and user rules | evaluate extracting a small always-loaded core; scope domains |
| Groundwork scope | engineering governance only | keep it this size |
| OpenSpec / ECC | proportional use; no duplication | unchanged |
| Execution model | main / subagent / team rule with fallback | observe live team use before any team hook |
| Context engineering | snapshot + delegation guidance | isolated-context defaults; native memory; no custom store |
| Continuity | repo-first order; **2.0**: one small, capped state file for non-OpenSpec-tracked work only (see §7) | OpenSpec-tracked work still has no separate state file — unchanged |
| Response style | completion block for engineering only | domain shapes; core principles move with the core |
| MCP | none required | approved list, least privilege, on demand |
| Safety | Git guard, review gate, deny lists, data framing | more deterministic guards, one per proven gap |
| Reproducibility | Groundwork versioned; toolkit mirrors user config | one reproducible harness definition |
| Evolution | — | validation-driven, SRE pilot first |
