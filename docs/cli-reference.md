# CLI Reference

The PhronEdge CLI lets you verify credentials, scan code for ungoverned tools, and export signed policies. All commands read `PHRONEDGE_API_KEY` and `PHRONEDGE_GATEWAY_URL` from environment variables.

## Installation

```bash
pip install phronedge
```

The `phronedge` command is available after installation.

## Commands

### phronedge verify

Verify your API key, gateway connection, and agent credential.

```bash
phronedge verify
phronedge verify --agent fraud-analyst
phronedge verify --agent agt-kyc-orch-v1
```

| Flag | Description |
|------|-------------|
| `--agent` | Agent ID to verify. Without this, returns the first available credential under your tenant |

**Output:**

```
PhronEdge Verify
==================================================
[+] API key: pe_live_xx******************xxxx
[+] Gateway: https://api.phronedge.com/api/v1

Testing gateway connection...
[+] Gateway reachable. 4 plans available.

Fetching credential...
[+] Credential valid
    Agent:        fraud-analyst
    Jurisdiction: DE
    Tools:        risk_report, customer_lookup, transaction_review

Ready. Your agent is governed.
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| 0 | Credential valid |
| 1 | API key not set, gateway unreachable, or credential fetch failed |

### phronedge export

Export the signed policy as OPA Rego, YAML, or JSON.

```bash
phronedge export rego
phronedge export yaml -o policy.yaml
phronedge export json --agent fraud-analyst
phronedge export rego --agent agt-kyc-orch-v1 -o kyc_policy.rego
```

| Argument | Description |
|----------|-------------|
| `format` | Required. One of: `rego`, `yaml`, `json` |

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Write to file instead of stdout |
| `--agent` | Agent ID to export. Without this, exports the first available credential |

**OPA Rego output includes:**
- Agent authorization rules
- Tool permission enforcement
- Jurisdiction validation
- Data classification checks
- PII detection patterns
- Behavioral baseline limits
- Delegation rules
- Output constraints
- Denial reason mapping
- Policy metadata with regulatory citations

### phronedge scan

Scan a Python file for tool functions and check which are governed by PhronEdge.

```bash
phronedge scan my_agent.py
phronedge scan my_agent.py --strict
```

| Argument | Description |
|----------|-------------|
| `file` | Required. Python file to scan |

| Flag | Description |
|------|-------------|
| `--strict` | Exit with code 1 if any ungoverned tools are found. Useful in CI/CD |

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

The scanner parses your Python file as an AST and finds functions that:
- Have a `@pe.govern()` decorator (governed)
- Have a docstring or `@tool` decorator but no `@pe.govern()` (ungoverned)
- Private functions (starting with `_`) are skipped

**CI/CD integration:**

```bash
phronedge scan src/agent.py --strict || exit 1
```

This fails the build if any tools are ungoverned.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PHRONEDGE_API_KEY` | Yes | Your API key starting with `pe_live_` |
| `PHRONEDGE_GATEWAY_URL` | No | Gateway URL. Defaults to `https://api.phronedge.com/api/v1` |
