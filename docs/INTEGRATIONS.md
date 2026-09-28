# Integration strategy (Groundwork 2.1)

Groundwork does not install, configure, or store credentials for any external system — that ownership belongs to the task's own environment (`docs/ARCHITECTURE.md`'s capability-ownership matrix, unchanged in 2.1). This document is the evidence Groundwork's capability-resolution model (`engineering-workflow.md` §6a) and the setup-time capability configurator point at: what's actually trustworthy, official, and safe to reach for, researched live (2026-09-28), not assumed. Wire any of these yourself, at whatever scope (`local`/`project`/`user`) and permission level fits your environment.

**Slack is deliberately not included** — not researched, not recommended, per explicit scope.

## Capability matrix

| Domain | Preferred access | Trust level | Read/Write | Auth model | Context strategy |
|---|---|---|---|---|---|
| GitHub | `github/github-mcp-server` (official) | Vendor/official | Full — including destructive; scope with `--read-only`/`--toolsets`/`--dynamic-toolsets` | OAuth, PAT, or GitHub App | Native toolset scoping + Tool Search defers unused schemas |
| Spacelift | Hosted MCP for conversational use; **prefer `spacectl`/direct GraphQL for scripted/CI changes** | Vendor/official | Read (`query`) + Write (`mutate` is a raw GraphQL pass-through — effectively the whole account's mutation surface, not curated per-action) | OAuth (browser) or `spacectl` bearer token (CI) | Small tool count (~5) via built-in `discover`, but `mutate`'s *capability* surface isn't reflected in that count — treat as high-trust-required |
| Jira (Atlassian) | `atlassian/atlassian-mcp-server` (official, GA 2026-02-04) | Vendor/official | Read (search/retrieve) + Write (create/update issues); delete/admin ops off by default | OAuth 2.1 (default) or API token | Native lazy/dynamic tool loading (small default set, rest on demand) |
| Confluence (Atlassian) | Same official server (Cloud only) — `sooperset/mcp-atlassian` (MIT, community) for Server/Data Center | Vendor/official (Cloud) · community (DC) | Read (pages/spaces) + Write (create/update — **full-body-replace only**, a known open issue can strip inline comment anchors on partial edits) | OAuth 2.1 or API token | Same as Jira |
| AWS | `awslabs/mcp` (official AWS Labs suite) | Vendor/official | Domain-dependent (aws-api, IaC/CDK, docs, pricing, support, Bedrock KB, etc.) | AWS credentials, scoped per server | Install only the sub-servers a profile actually needs |
| GCP | Google's newly-managed MCP servers (BigQuery, Compute Engine, GKE, Maps live; more "coming soon") | Vendor/official, but not Claude-specific-named by Google | Domain-dependent | Google Cloud auth | Managed/remote — enable per-service |
| Kubernetes | `containers/kubernetes-mcp-server` (Red Hat org) | Community/semi-official | kubectl-equivalent read/write | kubeconfig-based | No CNCF/vendor-single-official option found; scope by cluster/namespace access |
| Terraform | `hashicorp/terraform-mcp-server` (official HashiCorp) | Vendor/official | Plan/module/registry access; not a replacement for `terraform apply`'s own state safety | HashiCorp-managed | Bundled as an official plugin in Anthropic's own marketplace |
| Observability — Grafana | `grafana/mcp-grafana` (official, Apache-2.0, OSS) | Vendor/official | Read (query/dashboards) + Write (create/update dashboards, alerts) + destructive (`delete_dashboard`) — gate with `--disable-write` | Service-account token | Self-hosted, scope by instance |
| Observability — Datadog | Datadog-hosted MCP + official Claude Code plugin | Vendor/official | Read (logs/metrics/traces/incidents) + Write (e.g. monitor thresholds) | Vendor-managed (verify before adoption — public docs are thin on detail) | Managed/remote |
| Observability — PagerDuty | PagerDuty-hosted MCP (self-hosted variant deprecated) | Vendor/official | Large surface: 50 read tools, 22 write tools | Not fully confirmed — verify auth model before adoption | Scoping support unconfirmed; verify before wholesale enable |
| Observability — Sentry | `getsentry/sentry-mcp` + official Claude Code plugin | Vendor/official (source-available FSL license — not permissive OSS today; check org policy) | Read (issues/traces/Seer RCA) + narrow, confirmation-gated write | Token-based | Curated "Tool Pack" via the official plugin |
| Observability — Prometheus | **CLI/API preferred** — query the stable HTTP/PromQL API directly | No credible single official MCP found (CNCF project, no single vendor) | Read-only in practice | Network-gated | An MCP layer here adds trust/maintenance cost without real new capability |

## Why MCP/CLI, not "install everything"

Both Anthropic (`anthropic.com/engineering/code-execution-with-mcp`, 2025-11-04) and Claude Code's own current docs describe MCP tool-schema bloat as a real, named problem, and both describe the fix Groundwork relies on rather than reimplementing: **progressive disclosure and on-demand tool search**. Claude Code ships this as **Tool Search**, on by default — directly observed operating in this project's own sessions (a listing of dozens of MCP tools by name only, schemas fetched on demand). A concrete illustration from third-party measurement: a fully-loaded GitHub MCP server alone (93 tools) costs roughly 55,000 tokens; three such servers loaded wholesale would burn over 70% of a 200K context window before any task-specific work happens. This is exactly why the matrix above prefers scoped installs (GitHub's own `--toolsets`/`--read-only`/`--dynamic-toolsets`, Grafana's `--disable-write`, per-server enable/disable in `~/.claude.json`) over "connect everything, always on."

## Recommendation, in one line per domain

Connect only what a task genuinely needs, prefer a vendor-official server when one exists, prefer a narrow CLI/API call over a broad MCP mutation tool when the MCP tool is a thin pass-through anyway (Spacelift's `mutate`, Prometheus generally), and treat any domain marked "verify before adoption" above as exactly that — researched enough to know it exists and roughly what it does, not verified enough to install blind.
