# Harness landscape: what the best-known harnesses have in common

Research date 2026-11-08. Purpose: learn from well-known coding-agent harnesses before deciding each component in
`TRACKER.md`.

Source quality labels:
- **PRIMARY**: the vendor's own page or repo, read directly this session.
- **SECONDARY**: search-result summaries or third-party write-ups; not verified against the original.

Not read: openai.com, aider.chat and swe-agent.com were blocked by this session's network policy (DNS failure).
Their rows below are SECONDARY.

## Harnesses reviewed

| Harness | Key ideas | Source quality |
|---|---|---|
| Anthropic: long-running agents | Initializer agent sets up `init.sh`, a progress file and a JSON feature list; coding agent does one feature per session, commits, leaves clean state; start-of-session routine (read progress + git log, run init + a basic e2e check); judge completion by tests, not self-report | PRIMARY ([post](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)) |
| Anthropic: planner / generator / evaluator | Separate evaluator because agents "reliably skew positive when grading their own work"; explicit grading criteria; "sprint contract" agreeing on done before coding; "every component in a harness encodes an assumption about what the model can't do on its own", so remove parts one at a time as models improve | PRIMARY ([post](https://www.anthropic.com/engineering/harness-design-long-running-apps)) |
| Anthropic: building effective agents | Workflows vs agents; patterns: prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer; "finding the simplest solution possible, and only increase complexity when needed"; invest in the agent-computer interface (tool docs and tests) | PRIMARY ([post](https://www.anthropic.com/engineering/building-effective-agents), Dec 2024) |
| Claude Code best practices | CLAUDE.md: "Only write down what Claude can't find by reading the repo", under ~200 lines; "Give Claude something it can run that comes back pass or fail"; a rule Claude keeps missing "belongs in a hook"; Stop hook can block; subagents cost mostly tokens, restrict reviewer tools | PRIMARY ([docs](https://code.claude.com/docs/en/best-practices)) |
| GitHub Spec Kit | Constitution once per project; then specify → plan → tasks → implement → converge per feature; review each step | PRIMARY ([repo](https://github.com/github/spec-kit)) |
| Superpowers (obra) | Composable skills as "mandatory workflows": brainstorm → worktree → plan (2–5 minute tasks) → subagent per task → TDD → code review → finish branch; "Evidence over claims" | PRIMARY ([repo](https://github.com/obra/superpowers)); its own release notes report plan/spec review loops doubled time without measurable gain (`docs/research/HARNESS-METHODS-2026-10-28.md`) |
| OpenAI Codex | Agent loop ends a turn on an assistant message; AGENTS.md discovered root → cwd; harness-engineering team kept AGENTS.md ~100 lines as a map to deeper docs, with mechanical enforcement (linters, tests) | SECONDARY ([loop post](https://openai.com/index/unrolling-the-codex-agent-loop), [summary](https://zby.github.io/commonplace/sources/harness-engineering-leveraging-codex-agent-first-world)) |
| SWE-agent (Princeton) | The interface matters as much as the model: linter blocks invalid edits, file viewer ~100 lines per turn, concise search output | SECONDARY ([paper](https://arxiv.org/abs/2405.15793), [ACI docs](https://princeton-nlp.github.io/SWE-agent/background/aci)) |
| OpenHands | Event-sourced action/observation log (replayable); condenser summarizes history at context limits; sandboxed workspace | SECONDARY ([paper](https://arxiv.org/abs/2511.03690), [SDK docs](https://docs.openhands.dev/sdk/arch/sdk)) |
| Aider | tree-sitter repo map ranked by relevance within a token budget; architect (reasoning) + editor model split | SECONDARY ([wiki](https://agentwiki.org/aider)) |
| Cline | Plan mode (no file changes) vs Act mode; checkpoints for rollback; optional different models per mode | SECONDARY ([docs](https://docs.cline.bot/core-workflows/plan-and-act)) |
| Kiro (AWS) | Specs: requirements (EARS acceptance criteria) → design → tasks linked to requirements; steering files for persistent context; event hooks | SECONDARY ([SD Times](https://sdtimes.com/?p=57508)) |
| GSD | Fresh context per task to avoid "context rot"; phases with clear boundaries | SECONDARY ([guide](https://dev.to/alikazmidev/the-complete-beginners-guide-to-gsd-get-shit-done-framework-for-claude-code-24h0)) |
| Cognition (Devin) | "Don't build multi-agents": parallel writers make conflicting decisions from partial context; context engineering over agent swarms | SECONDARY ([summary](https://echai.ventures/how-founders-use-ai/ai-agents/should-i-build-one-agent-or-a-team-of-agents-working-together)) |

## What they have in common (ranked by how many harnesses share it)

| # | Common pattern | Seen in | Evidence strength | Component |
|---|---|---|---|---|
| P1 | **Ground-truth verification, not self-report**: tests, linters, pass/fail checks decide "done" | Anthropic (all 3), Claude Code, Superpowers, SWE-agent, OpenAI, Aider | Strong: Anthropic "dramatically improved performance"; SWE-agent ablation (secondary) | C11, C13 |
| P2 | **Plan before acting**, separate from doing | Claude Code, Cline, Spec Kit, Kiro, Superpowers, Aider architect, Anthropic planner | Practice; consistent across vendors | C3, C5 |
| P3 | **Short instruction file as a map**, details on demand | Claude Code (<200 lines), OpenAI (~100 lines), Spec Kit constitution, Kiro steering | Practice; OpenAI and Anthropic both warn big files crowd out the task | C1, C14 |
| P4 | **Specs as files in the repo**: requirements → design → tasks | Spec Kit, Kiro, OpenSpec, Superpowers, Anthropic feature list | Practice | C5 |
| P5 | **Context hygiene**: fresh context per task, condense history, concise tool output | GSD, Superpowers, OpenHands, SWE-agent, Aider repo map, Claude Code `/clear` | Moderate (OpenHands cost claim is the authors') | C9, C14 |
| P6 | **Durable progress artifacts** for continuity: progress file, feature list, tasks, git history | Anthropic long-running, Spec Kit, Kiro, Cline memory bank | Practice | C15, C16 |
| P7 | **Separate evaluator / reviewer** with explicit criteria | Anthropic planner/generator/evaluator, Superpowers, Claude Code | Moderate; but Superpowers' own data: extra review loops cost ~2x time, no gain | C12 |
| P8 | **Small increments + frequent commits / checkpoints** for rollback | Anthropic, Aider, Cline, Claude Code rewind | Practice | C10, C16 |
| P9 | **Deterministic enforcement** for must-happen rules (hooks, linters) | Claude Code, Kiro hooks, OpenAI mechanical enforcement, SWE-agent linter | Practice; Claude Code docs say missed rules belong in hooks | C7, C8 |
| P10 | **Good tool interface (ACI)**: few, well-documented tools, compact outputs | Anthropic, SWE-agent, OpenHands | Moderate (SWE-agent paper) | C6 |
| P11 | **Single writer**: subagents for reading, research and review; avoid parallel writers | Cognition, Claude Code, Superpowers (sequential tasks) | Practice | C9 |
| P12 | **Start simple, remove parts as models improve** | Anthropic (2 posts) | Stated principle, from the model vendor | All |

## Value for our harness

| Lesson | What it means for us | Affects draft |
|---|---|---|
| P12 + P3 | Our deconstruction is the right move. Keep always-on rules as a short map (target ≤ ~200 lines / ~4 KB) | C1, C14 |
| P1 + P9 | The evidence gate and verification must be deterministic (Stop hook, tests), not rule text | C7, C11, C13 |
| P7 with Superpowers' data | Independent review only for T3/T4, one round by default, explicit must-fix criteria; not for every change | C12 |
| P6 | Add a durable progress artifact for long work (OpenSpec `tasks.md` + brief), checked at session start | C15, C16 |
| P11 | Subagents read, explore and review; one main session writes | C9 |
| Sprint contract (Anthropic) | Agree "what done looks like" (acceptance checks) before implementing T2+ | C5, C11 |
| P5 | Fresh context per large task; keep tool outputs short | C14 |
| P10 | Prefer fewer, sharper tools and MCP servers | C6 |
| Gap | None of these harnesses publishes a controlled benchmark against plain usage. Our C21 evaluation would be a differentiator | C21 |
