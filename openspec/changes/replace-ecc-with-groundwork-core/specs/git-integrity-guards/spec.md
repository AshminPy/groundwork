## Purpose

Stop Claude from quietly bypassing or weakening a project's own checks: the git hooks a commit or push would run, and the linter or formatter configuration that defines what "passing" means.

## ADDED Requirements

### Requirement: Bypassing git hooks is blocked
A shell command SHALL be denied before it runs when a git segment (including inside `bash -c`, `sh -c` or `eval`) is:
- `commit`, `push`, `merge`, `rebase`, `am`, `cherry-pick` or `revert` with `--no-verify`;
- `commit` with `-n`, or with `n` inside a short-flag cluster before any value-taking letter (`m`, `F`, `C`, `c`, `t`, `S`, `u`);
- any git command with `-c core.hooksPath=<value>` or `--config-env=core.hooksPath=<var>`, the key matched case-insensitively;
- any git command preceded by an environment assignment `GIT_CONFIG_KEY_<n>=core.hooksPath`.

The deny reason SHALL tell Claude to fix what the hook reports and that the owner can run the command themselves.

#### Scenario: No-verify commit
- **WHEN** Claude runs `git commit --no-verify -m x`
- **THEN** the command does not run and Claude receives the deny reason

#### Scenario: Short-flag clusters
- **WHEN** Claude runs `git commit -an -m x` or `git commit -nm x`
- **THEN** the command does not run

#### Scenario: Hooks path override
- **WHEN** Claude runs `git -c core.HooksPath=/dev/null push origin feature/x` or `GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null git commit -m x`
- **THEN** the command does not run

#### Scenario: Inside a shell string
- **WHEN** Claude runs `bash -c 'git commit --no-verify -m x'`
- **THEN** the command does not run

#### Scenario: Ordinary commands are not affected
- **WHEN** Claude runs `git commit -m "fix: no-verify docs"`, `git commit -mn`, `git push -n origin feature/x`, `git merge -n main` or `git log -n 5`
- **THEN** the command runs without a prompt or denial

#### Scenario: Unparseable command mentioning a bypass
- **WHEN** a command contains `no-verify` or `hookspath` (any case) and the shell parser cannot split it into segments
- **THEN** the command does not run

### Requirement: Setting a repository hooks path asks first
`git config [--local|--global] core.hooksPath <value>` SHALL ask the owner before it runs.

#### Scenario: Husky setup
- **WHEN** Claude runs `git config core.hooksPath .husky`
- **THEN** the owner is asked before it runs

### Requirement: Editing an existing linter or formatter config asks first
An Edit, Write, MultiEdit or NotebookEdit SHALL ask the owner before it runs when the target's basename, compared case-insensitively, is one of: `.eslintrc`, `.eslintrc.js`, `.eslintrc.cjs`, `.eslintrc.json`, `.eslintrc.yml`, `.eslintrc.yaml`, `eslint.config.js`, `eslint.config.mjs`, `eslint.config.cjs`, `eslint.config.ts`, `eslint.config.mts`, `eslint.config.cts`, `.prettierrc`, `.prettierrc.js`, `.prettierrc.cjs`, `.prettierrc.json`, `.prettierrc.yml`, `.prettierrc.yaml`, `prettier.config.js`, `prettier.config.cjs`, `prettier.config.mjs`, `biome.json`, `biome.jsonc`, `.ruff.toml`, `ruff.toml`, `.shellcheckrc`, `.stylelintrc`, `.stylelintrc.json`, `.stylelintrc.yml`, `.markdownlint.json`, `.markdownlint.yaml`, `.markdownlintrc`; and the path exists (a dangling symlink, or a path that cannot be checked for a reason other than "not found", counts as existing). Creating such a file where nothing exists SHALL NOT ask. In a headless run the ask is a denial.

#### Scenario: Weakening an existing ruff config
- **WHEN** Claude edits an existing `ruff.toml`
- **THEN** the owner is asked before the edit is applied

#### Scenario: Case and symlinks
- **WHEN** Claude edits `Ruff.TOML`, or writes to `.eslintrc.js` that is a dangling symlink
- **THEN** the owner is asked

#### Scenario: New project config
- **WHEN** Claude writes `ruff.toml` in a folder where it does not exist
- **THEN** the write runs without a prompt

#### Scenario: Files outside the list
- **WHEN** Claude edits `pyproject.toml` or `.markdownlint-cli2.yaml`
- **THEN** this requirement does not ask

### Requirement: The guards are fast and local
Each guard SHALL make no network call and SHALL finish within 200 ms at the 90th percentile over its test inputs.

#### Scenario: Timing
- **WHEN** each guard is run in-process on 200 recorded test inputs
- **THEN** the 90th-percentile time is at most 200 ms and no socket is opened
