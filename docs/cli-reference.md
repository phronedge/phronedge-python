# CLI Reference

The PhronEdge CLI is the developer and CI/CD surface for policy management, agent operations, and chain verification. It covers 11 commands across 4 command groups and 3 standalone commands.

All commands read `PHRONEDGE_API_KEY` and `PHRONEDGE_GATEWAY_URL` from environment variables.

## Installation

```bash
pip install phronedge
```

The `phronedge` command is available after installation.

## Command groups

| Group | Commands | Purpose |
|-------|----------|---------|
| `policy` | `build`, `deploy`, `status` | Sign policies, deploy credentials, show registry |
| `agent` | `list`, `quarantine`, `reinstate` | Agent inventory and lifecycle |
| `chain` | `verify`, `events` | Audit chain inspection |
| Standalone | `verify`, `scan`, `export` | Credential check, code scan, policy export |

## Authentication

Set your API key once per shell:

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
```

For enterprise self-hosted deployments, point the CLI at your gateway:

```bash
export PHRONEDGE_GATEWAY_URL=https://phronedge.yourbank.internal/api/v1
```

## policy

Sign, deploy, and inspect governance policies.

### policy build

Sign a policy for review. Credentials are **not** issued. Use this for CI preview and pre-merge validation.

```bash
phronedge policy build policy.yaml
phronedge policy build policy.yaml -o signed_policy.json
```

| Argument | Description |
|----------|-------------|
| `file` | Required. Path to `policy.yaml` or `policy.json` |

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Write the signed artifact to a file |
| `--json` | Treat the input file as JSON instead of YAML |

**Output:**

```
PhronEdge Policy Build
==================================================

[+] Policy parsed: policy.yaml
[+] Compliance evaluation: PASS
    Controls met:    30/30
    Frameworks:      GDPR, EU AI Act, ISO 42001, NIST AI RMF, NAIC, ...
[+] Signed (ES256 key=v2)
    Policy hash: 6b890f03c36256dfc5f062895f2afd3b...

Preview only. No credentials issued.
Run 'phronedge policy deploy' to issue credentials.
```

### policy deploy

Sign the policy **and** issue credentials. Agents become governable as soon as this completes.

```bash
phronedge policy deploy policy.yaml
phronedge policy deploy policy.json --json
```

| Argument | Description |
|----------|-------------|
| `file` | Required. Path to `policy.yaml` or `policy.json` |

| Flag | Description |
|------|-------------|
| `--json` | Treat the input file as JSON instead of YAML |

**Output:**

```
PhronEdge Policy Deploy
==================================================

[+] Policy parsed: policy.yaml
[+] Compliance evaluation: PASS
[+] Signed (ES256 key=v2)
[+] Credentials issued: 1
    claims-investigator: cred-claims-investigator-3d8ecfb6
[+] Tools registered: 2
    claim_lookup, report_generate
[+] Events anchored to chain

Ready. Tools are now governed.
```

**What gets anchored:**

- `POLICY_SIGNED` (once per policy)
- `AGENT_REGISTERED` (once per agent)
- `CREDENTIAL_ISSUED` (once per agent)
- `TOOL_REGISTERED` (once per tool)

### policy status

Show all signed policies, registered agents, and permitted tools under your tenant.

```bash
phronedge policy status
```

**Output:**

```
PhronEdge Policy Registry
==================================================

Active policy
  Hash:       6b890f03c36256dfc5f062895f2afd3b...
  Signed at:  2026-04-17 18:42:05
  Key:        v2 (active)
  Controls:   30/30

Agents (5)
  claims-investigator    T2  3 tools   ACTIVE
  test-cli-agent         T2  1 tool    ACTIVE
  agt-risk-orch-v1       T2  5 tools   ACTIVE  (2 sub-agents)
  agt-aml-v1             T1  1 tool    ACTIVE
  agt-trial-orch-v1      T1  2 tools   ACTIVE  (1 sub-agent)

Tools (9)
  claim_lookup           PII  [DE, AT, CH]  read
  patient_search         PHI  [DE]          read
  ...
```

## agent

Agent inventory and lifecycle management.

### agent list

List every agent under the tenant with tier, tool count, and state.

```bash
phronedge agent list
```

**Output:**

```
PhronEdge Agents
==================================================
  [+] claims-investigator
      Tier: T2  Tools: 3  State: ACTIVE

  [+] agt-risk-orch-v1
      Tier: T2  Tools: 5  State: ACTIVE  Sub-agents: 2

  [x] agt-adverse-v1
      Tier: T1  Tools: 2  State: QUARANTINED
      Reason: Behavioral anomaly (22x baseline)
```

**Agent states:**

| State | Meaning | Recoverable |
|-------|---------|-------------|
| ACTIVE | Normal operation. All checkpoints active. | N/A |
| QUARANTINED | All tool calls blocked. Credential preserved. | Yes, with `phronedge agent reinstate` |
| KILLED | Permanent termination. Credential revoked. Agent ID cannot be reused. | No |

### agent quarantine

Suspend an agent. All tool calls are blocked immediately. Reversible.

```bash
phronedge agent quarantine claims-investigator "Incident 4521: investigating data leak"
```

| Argument | Description |
|----------|-------------|
| `agent_id` | Required. Agent to quarantine |
| `reason` | Required. Incident reference or justification |

Anchors `AGENT_QUARANTINED` event to the chain with the reason and initiator.

### agent reinstate

Restore a quarantined agent to active state. No-op on killed agents.

```bash
phronedge agent reinstate claims-investigator "Incident 4521 closed: false positive"
```

| Argument | Description |
|----------|-------------|
| `agent_id` | Required. Agent to reinstate |
| `reason` | Required. Justification |

Anchors `AGENT_REINSTATED` event to the chain.

**Kill switch is not available via CLI.** Kill is permanent and irreversible. The Console at `phronedge.com/brain` is the only surface for killing an agent.

## chain

Inspect and verify the audit chain.

### chain verify

Recompute every event hash and confirm the chain is intact.

```bash
phronedge chain verify
```

**Output when chain is clean:**

```
PhronEdge Chain Verify
==================================================

[+] Events:  342
[+] Genesis: 2026-04-17 11:22:05
[+] Latest:  2026-04-17 18:58:06
[+] Walking chain from newest to oldest...
[+] All hashes match. Chain is intact.

Chain valid.
```

**Output when chain is broken:**

```
PhronEdge Chain Verify
==================================================

[+] Events:  342
[x] Break detected at event 237
    Expected prev_hash: a7f3b2c9d1e4f5a6
    Actual prev_hash:   0000000000000000
    Event type:         TOOL_CALL_ALLOWED
    Timestamp:          2026-04-16 09:14:22

Chain tampered. Evidence preserved. Contact security.
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Chain valid |
| 1 | Break detected |
| 2 | Gateway unreachable |

### chain events

Show the most recent events in the audit chain.

```bash
phronedge chain events
phronedge chain events --limit 10
phronedge chain events --limit 100 --agent claims-investigator
phronedge chain events --type TOOL_CALL_BLOCKED
```

| Flag | Default | Description |
|------|---------|-------------|
| `--limit` | 50 | Number of events to return |
| `--agent` | all | Filter by agent ID |
| `--type` | all | Filter by event type |

**Output:**

```
PhronEdge Chain Events
==================================================

TIME             EVENT                   AGENT                  DETAIL
18:58:06.556     TOOL_CALL_BLOCKED       test-cli-agent         Action 'delete' not permitted on 'claim_lookup'
18:58:02.892     TOOL_CALL_BLOCKED       test-cli-agent         Tool 'adverse_events' not in permitted_tools
18:57:59.857     TOOL_CALL_BLOCKED       test-cli-agent         Jurisdiction 'DE' not permitted for 'claim_lookup'
18:56:18.655     TOOL_CALL_BLOCKED       test-cli-agent         Jurisdiction 'RU' not permitted for 'claim_lookup'
18:56:13.423     TOOL_CALL_ALLOWED       claims-investigator    claim_lookup read DE
18:42:05.321     POLICY_SIGNED           system                 hash=6b890f03c36256dfc5f062895f2afd3b...
18:42:05.318     CREDENTIAL_ISSUED       claims-investigator    cred-claims-investigator-3d8ecfb6
18:42:05.312     AGENT_REGISTERED        claims-investigator    tier=T2 role=standalone

50 events displayed.
Chain valid. Use 'phronedge chain verify' for full check.
```

## export

Export the signed policy as deployable governance artifacts.

```bash
phronedge export rego --agent claims-investigator -o policy.rego
phronedge export yaml --agent claims-investigator -o policy.yaml
phronedge export json --agent claims-investigator -o policy.json
```

| Argument | Description |
|----------|-------------|
| `format` | Required. One of: `rego`, `yaml`, `json` |

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Write to file instead of stdout |
| `--agent` | Agent ID to export. Without this, exports the first available credential |

### OPA Rego export

The Rego bundle contains 9 enforcement rules that mirror the gateway checkpoints:

| Rule | Enforces |
|------|----------|
| `agent_authorized` | Agent is registered in the signed policy |
| `tool_permitted` | Tool is in the agent's permitted_tools |
| `data_classification_valid` | Agent clearance meets or exceeds tool data class |
| `jurisdiction_valid` | Call jurisdiction is in the tool's allowed list |
| `tier_sufficient` | Agent tier meets tool minimum tier |
| `within_baseline` | Call rate is within behavioral baseline |
| `model_allowed` | Model is in the permitted_models list |
| `delegation_valid` | Delegation target is in can_delegate_to |
| `human_oversight` | Human approval is satisfied where required |

Drop the Rego into any OPA runtime for independent enforcement outside PhronEdge.

### Why export

- **Version control.** Commit `policy.yaml` to git. Review policy changes in pull requests.
- **Independent enforcement.** Load `policy.rego` into an OPA instance on your infrastructure.
- **Regulatory audit.** Hand `policy.json` to an auditor. Hash of the artifact is anchored in the chain.
- **Disaster recovery.** Re-import a signed policy if your local state is lost.

## Standalone commands

### phronedge verify

Verify that a specific agent's credential is live and signed correctly.

```bash
phronedge verify
phronedge verify --agent claims-investigator
```

| Flag | Description |
|------|-------------|
| `--agent` | Agent ID to verify. Without this, verifies the first available credential |

**Output:**

```
PhronEdge Verify
==================================================

[+] API key: pe_live_xx******************xxxx
[+] Gateway: https://api.phronedge.com/api/v1

Testing gateway connection...
[+] Gateway reachable

Verifying agent: claims-investigator
[+] Credential valid
    Agent:        claims-investigator
    Tier:         T2
    Jurisdiction: DE
    Tools:        claim_lookup, report_generate
    Signed:       ES256 key=v2

Ready. Agent 'claims-investigator' is governed.
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Credential valid |
| 1 | Authentication or credential fetch failed |

### phronedge scan

Parse a Python file and report which tools are governed with `@pe.govern()` and which are not.

```bash
phronedge scan my_agent.py
phronedge scan my_agent.py --strict
phronedge scan src/agents/*.py --strict
```

| Argument | Description |
|----------|-------------|
| `file` | Required. Python file (or glob) to scan |

| Flag | Description |
|------|-------------|
| `--strict` | Exit with code 1 if any ungoverned tools are found. Use in CI. |

**Output:**

```
PhronEdge Scan: my_agent.py
==================================================

  [+] claim_lookup (as "claim_lookup")    line  12  governed
  [+] report_generate (as "report")       line  18  governed
  [x] send_email                          line  24  NOT governed

Total: 3 tools
  Governed:   2
  Ungoverned: 1

Ungoverned tools execute without governance.
Add @pe.govern("tool_name") to each one.
```

**How scan works:**

The scanner parses the file as an AST. It flags functions that have a `@tool` decorator (from LangChain, CrewAI, OpenAI Agents, etc.) or a clear docstring signature, and checks for a `@pe.govern()` decorator on the same function. Functions starting with `_` (private) are skipped.

## CI/CD integration

A complete governance CI pipeline:

```yaml
name: Governance
on:
  pull_request:
  push:
    branches: [main]

env:
  PHRONEDGE_API_KEY: ${{ secrets.PHRONEDGE_API_KEY }}

jobs:
  validate:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install phronedge
      - run: phronedge scan src/agents/*.py --strict
      - run: phronedge policy build governance/policy.yaml
      - run: phronedge chain verify

  deploy:
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install phronedge
      - run: phronedge policy deploy governance/policy.yaml
      - run: phronedge export rego -o governance/policy.rego
      - run: phronedge chain verify
```

**What this proves:**

1. Every policy change goes through version control.
2. No policy deploys without pull request approval.
3. Every deployment is auditable (git commit plus chain event).
4. The audit trail is tamper-evident (chain verify in CI).
5. The OPA rules are independently verifiable (Rego artifact in repo).

## Global flags

| Flag | Description |
|------|-------------|
| `-h`, `--help` | Show command help. Available on every command and subcommand. |

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PHRONEDGE_API_KEY` | Yes | API key starting with `pe_live_` |
| `PHRONEDGE_GATEWAY_URL` | No | Gateway URL. Defaults to `https://api.phronedge.com/api/v1` |
| `PHRONEDGE_AGENT_ID` | No | Default agent for `verify`, `export`, and lifecycle commands |

## Next steps

- [Quickstart](/docs/quickstart). End-to-end example
- [SDK reference](/docs/sdk). Python API for runtime governance
- [REST API reference](/docs/api). HTTP endpoints for non-Python clients
- [Console guide](/docs/console). Visual Policy Builder and Observer
- [Enterprise deployment](/docs/enterprise-deployment). Self-hosted CLI with your gateway
