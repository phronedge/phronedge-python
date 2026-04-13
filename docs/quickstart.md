# Quickstart

Govern your first AI agent in under 2 minutes.

## Install

```bash
pip install phronedge
```

Requires Python 3.9 or higher. Works with any framework. No additional dependencies.

## Get an API key

1. Go to [phronedge.com/brain](https://phronedge.com/brain) and sign in
2. Open **API Keys** in the sidebar
3. Click **Create Key**
4. Copy the key. It starts with `pe_live_` and is shown only once

## Set your API key

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
```

Never hardcode API keys in your source code. Use environment variables or your secrets manager.

## How PhronEdge works

**Your data stays in your runtime.** PhronEdge validates governance decisions, not your business data. Your function arguments, return values, and model outputs never leave your infrastructure. The gateway sees the tool name, action, and jurisdiction.

**Your policy is yours.** After signing, the ECDSA credential lives in your agent runtime. Export it as OPA Rego and run it independently. If PhronEdge goes offline, your signed credential still works.

**Under 50ms at any scale.** No queue. No batch. No cold start. Millions of governed calls per day with the same latency as the first.

199 jurisdictions. 30 controls. ECDSA P-256 signatures. SHA-256 hash-chained audit trail.

## Govern your first tool

This is the simplest possible governed tool. One decorator. Nothing else.

```python
from phronedge import PhronEdge

pe = PhronEdge()

@pe.govern("lookup_claim")
def lookup_claim(claim_id: str) -> str:
    """Look up an insurance claim by ID."""
    return db.query(claim_id)

# This call now passes through 7 governance checkpoints
# before the function body executes. Under 50ms.
result = lookup_claim("CLM-2026-001")
```

When `lookup_claim` is called, PhronEdge intercepts it, validates the agent credential against 7 checkpoints, and either allows or blocks the call. If allowed, the function runs normally and the result is returned. If blocked, the function never executes.

## Per-tool permissions

Each tool call can specify an `action` and a `jurisdiction`. The `action` controls what the tool is allowed to do. The `jurisdiction` controls where it is allowed to operate.

```python
pe = PhronEdge()

# Read-only access in Germany
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> dict:
    return claims_db.get(claim_id)

# Write access in Germany
@pe.govern("update_claim", action="write", jurisdiction="DE")
def update_claim(claim_id: str, data: dict) -> dict:
    return claims_db.update(claim_id, data)
```

### Decorator parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool_name` | str | required | Must match a tool in your signed policy |
| `action` | str | `"execute"` | `read`, `write`, `delete`, or `execute` |
| `jurisdiction` | str | None | ISO alpha-2 code like `DE`, `US`, `GB` |
| `mcp` | str | None | MCP server URL for tool discovery |
| `delegates` | list | None | Agent IDs this call can delegate to |

### Jurisdiction enforcement

The allowed jurisdictions for each tool are defined as a list when you sign the policy. The `jurisdiction` parameter in the decorator tells the gateway which jurisdiction this specific call is operating in. The gateway checks if it is in the allowed list.

For example, if your policy defines `claim_lookup` with `jurisdictions: ["DE", "AT", "CH"]`:

```python
pe = PhronEdge(agent_id="claims-investigator")

# Allowed: DE is in the policy list ["DE", "AT", "CH"]
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def lookup_de(claim_id):
    return claims_db.get(claim_id)

# Allowed: AT is also in the list
@pe.govern("claim_lookup", action="read", jurisdiction="AT")
def lookup_at(claim_id):
    return claims_db.get(claim_id)

# Blocked: CN is not in the list
@pe.govern("claim_lookup", action="read", jurisdiction="CN")
def lookup_cn(claim_id):
    return claims_db.get(claim_id)  # never executes
```

You define the allowed jurisdictions per tool when you sign your policy:

```python
"tools": [{
    "id": "claim_lookup",
    "jurisdictions": ["DE", "AT", "CH"],
    ...
}]
```

## Multiple agents, one API key

If you have multiple agents under the same tenant, use `agent_id` to specify which one:

```python
# Agent 1: fraud analyst
pe_fraud = PhronEdge(agent_id="fraud-analyst")

@pe_fraud.govern("transaction_review", action="read", jurisdiction="DE")
def review_transaction(txn_id: str) -> dict:
    return txn_db.get(txn_id)

# Agent 2: KYC verifier (different tools, different clearance)
pe_kyc = PhronEdge(agent_id="agt-kyc-orch-v1")

@pe_kyc.govern("id_verify", action="read", jurisdiction="DE")
def verify_identity(doc_id: str) -> dict:
    return idv_service.verify(doc_id)
```

One API key. Each `PhronEdge` instance fetches the credential for its specific agent. Different agents have different tools, different clearances, different jurisdictions.

## What happens on every call

```
Your code calls a governed function
  |
  v
PhronEdge SDK intercepts before execution
  |
  v
Gateway runs 7 checkpoints in under 50ms:
  1. Credential validation   - ECDSA P-256 signature verified
  2. Tool permission         - Is this tool in the signed credential?
  3. Data classification     - Does agent clearance match the data level?
  4. PII detection           - Input scanned for personal data
  5. Jurisdiction check      - Is this jurisdiction allowed for this tool?
  6. Behavioral analysis     - Is this call within normal baseline?
  7. Output constraints      - Response scanned before return
  |
  v
ALLOW: function executes, result returned, event anchored to audit chain
BLOCK: function never executes, regulation cited, event anchored to audit chain
```

## What a block looks like

When a tool call is blocked, you get structured data explaining why:

```python
from phronedge import PhronEdge

pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("claim_lookup", action="read", jurisdiction="CN")
def claim_lookup_china(claim_id):
    return db.query(claim_id)

result = claim_lookup_china("CLM-001")
# result = {
#     "blocked": True,
#     "reason": "Jurisdiction 'CN' blocked by organization policy.",
#     "checkpoint": "jurisdiction",
#     "retry": True,
#     "message": "Tool call blocked by PhronEdge governance."
# }
```

The function body never executes. The block is logged to your audit chain with the regulation that triggered it.

If you prefer exceptions instead of return values:

```python
from phronedge import PhronEdge, GovernanceError

pe = PhronEdge(agent_id="claims-investigator", raise_on_block=True)

@pe.govern("claim_lookup", action="read", jurisdiction="CN")
def claim_lookup_china(claim_id):
    return db.query(claim_id)

try:
    result = claim_lookup_china("CLM-001")
except GovernanceError as e:
    print(e.checkpoint)   # "jurisdiction"
    print(e.regulation)   # "GDPR Art. 44-49"
    print(e.reason)       # "Jurisdiction 'CN' blocked by organization policy."
```

## What an allow looks like

Allowed calls return the function result normally. In the console Observer you see:

```
Event:      TOOL_CALL_ALLOWED
Agent:      claims-investigator
Tool:       claim_lookup
Action:     read
Checkpoint: All 7 passed
Hash:       a7f3b2c9...
Prev Hash:  d1e4f5a6...
Regulation: GDPR Art. 5(1)(f), EU AI Act Art. 9
```

Every event is SHA-256 hashed and chained to the previous event. Tamper one and the chain breaks.

## Sign a policy

Before your tools can be governed, you need a signed policy. There are three ways:

**Console (recommended for first time):**

Go to [phronedge.com/brain](https://phronedge.com/brain), open the Policy Builder, define your agents and tools, and click Build and Deploy. After signing, the Architecture view shows your policy as JSON, YAML, and OPA Rego.

**API (for automation):**

```python
import os, requests

policy = {
    "organization": {
        "name": "Your Company",
        "jurisdiction": "DE",
        "industry": "IN",
        "data_types": ["PUB", "PII"],
        "data_residency": ["DE"],
        "deployment_jurisdictions": ["DE", "AT", "CH"],
    },
    "agents": [{
        "id": "my-agent",
        "purpose": "Process insurance claims",
        "model": "gpt-4o",
        "tier": "T2",
        "role": "standalone",
        "data_classifications": ["PUB", "PII"],
        "tools": ["claim_lookup", "report_generate"],
        "host_jurisdiction": "DE",
        "serving_jurisdictions": ["DE", "AT", "CH"],
    }],
    "tools": [
        {
            "id": "claim_lookup",
            "description": "Search claims by ID",
            "type": "sdk",
            "data_classification": "PII",
            "permissions": ["read"],
            "jurisdictions": ["DE", "AT", "CH"],
            "deny_patterns": ["DROP", "DELETE", "TRUNCATE"],
        },
        {
            "id": "report_generate",
            "description": "Generate compliance reports",
            "type": "sdk",
            "data_classification": "INT",
            "permissions": ["read", "write"],
            "jurisdictions": ["DE"],
        },
    ],
}

r = requests.post(
    "https://api.phronedge.com/api/v1/governance/build",
    headers={
        "X-PhronEdge-Key": os.environ["PHRONEDGE_API_KEY"],
        "Content-Type": "application/json",
    },
    json=policy,
)

result = r.json()
print(result["status"])                           # "compliant"
print(result["signed_artifact"]["controls_met"])  # 30
```

**CLI:**

```bash
phronedge verify --agent my-agent
```

## Export your policy as code

After signing, export your policy as OPA Rego, YAML, or JSON:

```bash
phronedge export rego --agent fraud-analyst
phronedge export yaml --agent fraud-analyst -o policy.yaml
phronedge export json --agent fraud-analyst
```

From the console, go to Policy Builder, sign, then click the JSON, YAML, or OPA tabs in the Architecture view.

The Rego export is a complete OPA policy bundle with agent authorization, tool permissions, jurisdiction enforcement, tier controls, behavioral baselines, denial reasons, and regulatory citations. Drop it into any OPA runtime.

## Verify your setup

```bash
phronedge verify --agent my-agent
```

```
PhronEdge Verify
==================================================
[+] API key: pe_live_xx******************xxxx
[+] Gateway: https://api.phronedge.com/api/v1

Testing gateway connection...
[+] Gateway reachable. 4 plans available.

Fetching credential...
[+] Credential valid
    Agent:        my-agent
    Jurisdiction: DE
    Tools:        claim_lookup, report_generate

Ready. Your agent is governed.
```

## Scan your code

Check that all tools in your codebase are governed:

```bash
phronedge scan my_agent.py
```

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

## Full runnable example

This script registers an agent, signs a policy, runs governed tools, tests blocks, and checks the audit chain. Copy it, set your API key, and run it.

```python
"""
PhronEdge E2E: from zero to governed in one script.
pip install phronedge requests
"""
import os, json, logging, requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phronedge.e2e")

API = os.environ.get("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")
KEY = os.environ["PHRONEDGE_API_KEY"]
H = {"X-PhronEdge-Key": KEY, "Content-Type": "application/json"}

# 1. Sign policy
log.info("Signing policy...")
policy = {
    "organization": {
        "name": "Test Co",
        "jurisdiction": "DE",
        "industry": "IN",
        "data_types": ["PUB", "PII"],
        "data_residency": ["DE"],
        "deployment_jurisdictions": ["DE"],
    },
    "agents": [{
        "id": "test-agent",
        "purpose": "Test agent",
        "model": "gpt-4o",
        "tier": "T2",
        "role": "standalone",
        "data_classifications": ["PUB", "PII"],
        "tools": ["claim_lookup"],
        "host_jurisdiction": "DE",
        "serving_jurisdictions": ["DE"],
    }],
    "tools": [{
        "id": "claim_lookup",
        "description": "Search claims",
        "type": "sdk",
        "data_classification": "PII",
        "permissions": ["read"],
        "jurisdictions": ["DE"],
        "deny_patterns": ["DROP", "DELETE"],
    }],
}
r = requests.post(f"{API}/governance/build", headers=H, json=policy, timeout=30)
log.info("Status: %s", r.json().get("status"))

# 2. Govern and call
from phronedge import PhronEdge, GovernanceError

pe = PhronEdge(agent_id="test-agent", raise_on_block=True)

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id):
    return json.dumps({"id": claim_id, "status": "OPEN", "amount": 12500})

log.info("ALLOWED: %s", claim_lookup("CLM-001"))

# 3. Test block: wrong jurisdiction
@pe.govern("claim_lookup", action="read", jurisdiction="CN")
def bad_jurisdiction(claim_id):
    return "SHOULD NOT RUN"

try:
    bad_jurisdiction("CLM-001")
except GovernanceError as e:
    log.info("BLOCKED: %s", e)

# 4. Test block: SQL injection
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def bad_inject(query):
    return "SHOULD NOT RUN"

try:
    bad_inject("DROP TABLE claims")
except GovernanceError as e:
    log.info("BLOCKED: %s", e)

log.info("Done. Check phronedge.com/brain for the audit trail.")
```

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
python quickstart_e2e.py
```

Expected output:

```
08:30:00 INFO  Signing policy...
08:30:01 INFO  Status: compliant
08:30:03 INFO  ALLOWED: {"id": "CLM-001", "status": "OPEN", "amount": 12500}
08:30:04 INFO  BLOCKED: Jurisdiction 'CN' blocked by organization policy.
08:30:05 INFO  BLOCKED: Global deny pattern 'DROP TABLE' matched.
08:30:05 INFO  Done. Check phronedge.com/brain for the audit trail.
```

## Next steps

- [Framework guides](/docs/frameworks): LangGraph, CrewAI, Google ADK, and 6 more
- [Multi-agent governance](/docs/multi-agent): Delegation, sub-agents, chain governance
- [SDK reference](/docs/sdk): Every parameter, every method, every error
- [CLI reference](/docs/cli): scan, verify, export
- [REST API reference](/docs/api): Every endpoint with request and response examples
- [Console guide](/docs/console): Policy Builder, Observer, Architecture, Audit Log, OPA export
