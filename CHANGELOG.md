# Changelog

## 1.0.0 — 2026-09-03

Initial release, extracted from a real personal-harness migration onto ECC 2.2.1 + OpenSpec 1.12.0.

- `rules/engineering-workflow.md` — TRIVIAL/STANDARD/MATERIAL tiering, autonomy rule (six genuine owner-decision triggers, nothing else stops the loop), completion status block.
- `rules/evidence-policy.md` — evidence priority order, uncertainty labels, the DECISION format for material technical calls, the completion-evidence table (code ≠ tested ≠ merged ≠ deployed ≠ live validated).
- `hooks/block_protected_push.py` — denies `git push` to `main`/`master`/`production`/`prod`/`release` and any force-push, shell-chain aware.
- `hooks/require_material_review.py` — denies finishing a session with a fully-implemented, uncommitted OpenSpec change that no reviewer-shaped tool call ever touched. Added after an initial gap: a plain autonomy rule alone let a real test run finish a material feature with zero review dispatched.
- `install.sh` / `uninstall.sh`, `scripts/merge_settings.py` / `unmerge_settings.py` — idempotent, additive-only `settings.json` handling; never overwrites unrelated configuration.

See [docs/VALIDATION.md](docs/VALIDATION.md) for the test evidence this release is based on, including the fixes that came out of live testing (a `git status` untracked-directory edge case in the review gate; the removal of a generic MATERIAL-tier approval stop that contradicted the autonomy rule).
