# Quickstart

Govern your first AI agent in under 2 minutes.

PhronEdge enforces constitutional governance at the agent boundary. Every tool call passes through 7 checkpoints before execution. Every decision is hash-chained and cryptographically provable. Every policy build maps to EU AI Act Articles 9, 14, and 15. Every governed call produces an Article 12 audit event.

## Install

```bash
pip install phronedge
```

Requires Python 3.9 or higher. Works with any framework. No additional dependencies.

Current version: `2.4.6`

## Get an API key

1. Go to [phronedge.com/brain](https://phronedge.com/brain) and sign in
2. Open **API Keys** in the sidebar
3. Click **Create Key**
4. Copy the key. It starts with `pe_live_` and is shown only once

## Set your API key

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
```

Never hardcode API keys. Use environment variables or your secrets manager.

## How PhronEdge works

**Your data stays in your runtime.** PhronEdge validates governance decisions, not business data. Function arguments, return values, and model outputs never leave your infrastructure. The gateway sees the tool name, action, and jurisdiction.

**Your policy is cryptographically signed.** Every policy is ECDSA P-256 signed with your tenant's private key. The credential lives in your agent runtime. Export it as OPA Rego and run it independently. If PhronEdge is unreachable, your signed credential continues to govern.

**Gateway latency under 50ms.** No queue. No batch. No cold start. Millions of governed calls per day with the same latency as the first.

196 jurisdictions. 30 controls. 7 checkpoints. ECDSA P-256 signatures. SHA-256 hash-chained audit trail.

## Govern your first tool

One decorator. Nothing else.

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

When `lookup_claim` is called, PhronEdge intercepts it, validates the agent credential against 7 checkpoints, and either allows or blocks the call. If allowed, the function runs normally. If blocked, the function body never executes.

## Per-tool permissions

Each tool call specifies an `action` and a `jurisdiction`.

```python
pe = PhronEdge(agent_id="claims-investigator")

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

## Jurisdiction enforcement

The allowed jurisdictions for each tool are defined when you sign the policy. The `jurisdiction` parameter in the decorator declares which jurisdiction this specific call operates in. The gateway checks it against the allowed list.

If your policy defines `claim_lookup` with `jurisdictions: ["DE", "AT", "CH"]`:

```python
pe = PhronEdge(agent_id="claims-investigator")

# Allowed: DE is in the policy list
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def lookup_de(claim_id):
    return claims_db.get(claim_id)

# Allowed: AT is also in the list
@pe.govern("claim_lookup", action="read", jurisdiction="AT")
def lookup_at(claim_id):
    return claims_db.get(claim_id)

# Blocked: CN is not in the list. Function never executes.
@pe.govern("claim_lookup", action="read", jurisdiction="CN")
def lookup_cn(claim_id):
    return claims_db.get(claim_id)
```

## Data classifications

Every tool and every agent declares a data class. The gateway enforces that an agent's clearance matches or exceeds the tool's data class.

| Code | Label | Regulatory anchor |
|------|-------|-------------------|
| `PUB` | Public APIs, open data. No restrictions. | None |
| `INT` | Internal company data. Not for external sharing. | SOC 2, ISO 27001 |
| `PII` | Names, emails, addresses. | GDPR Art. 4(1) |
| `PHI` | Patient records, health data. | HIPAA, GDPR Art. 9 |
| `SPC` | Biometrics, credit scores, criminal records. | GDPR Art. 9 special categories |
| `FIN` | Payment data, bank accounts, transactions. | PCI DSS, PSD2 |
| `CON` | Trade secrets, legal privilege. Need-to-know only. | Trade Secrets Directive |
| `RST` | Classified, maximum protection. Regulatory approval required. | National security frameworks |

An agent with `INT` clearance cannot call a tool classified `PII`. The gateway blocks the call and cites the relevant regulation.

## Multiple agents, one API key

```python
# Agent 1: fraud analyst
pe_fraud = PhronEdge(agent_id="fraud-analyst")

@pe_fraud.govern("transaction_review", action="read", jurisdiction="DE")
def review_transaction(txn_id: str) -> dict:
    return txn_db.get(txn_id)

# Agent 2: KYC verifier. Different tools. Different clearance. Different jurisdictions.
pe_kyc = PhronEdge(agent_id="agt-kyc-orch-v1")

@pe_kyc.govern("id_verify", action="read", jurisdiction="DE")
def verify_identity(doc_id: str) -> dict:
    return idv_service.verify(doc_id)
```

One API key. Each `PhronEdge` instance fetches the credential for its specific agent.

## What happens on every call

The SDK intercepts before the function body executes. The gateway runs 7 checkpoints in under 50ms:

| # | Checkpoint | What it does |
|---|------------|--------------|
| 1 | Credential Validator | ECDSA P-256 signature, expiry, revocation cache |
| 2 | PII Detector | Scans input for personal data patterns |
| 3 | Jurisdiction Router | Maps applicable laws, blocks disallowed jurisdictions |
| 4 | Behavioral Baseline | Compares current rate to anchored baseline |
| 5 | Judge | RBAC plus ABAC plus contextual state. Permission and tier check |
| 6 | Data Classifier | Tags response classification |
| 7 | Output Constraint | Access-based restriction and redaction |

**ALLOW:** Function executes, result returned, `TOOL_CALL_ALLOWED` event anchored to the audit chain.

**BLOCK:** Function never executes, regulation cited, `TOOL_CALL_BLOCKED` event anchored to the audit chain.

## What a block looks like

When a tool call is blocked, the SDK returns structured data:

```python
from phronedge import PhronEdge

pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("claim_lookup", action="read", jurisdiction="CN")
def claim_lookup_china(claim_id):
    return db.query(claim_id)

result = claim_lookup_china("CLM-001")
# result = {
#     "blocked": True,
#     "reason": "Jurisdiction 'CN' not permitted for tool 'claim_lookup'. Allowed: DE, AT, CH",
#     "checkpoint": "jurisdiction",
#     "regulation": "GDPR Art. 44-49",
#     "retry": True,
#     "message": "Tool call blocked by PhronEdge governance."
# }
```

The function body never executes. The block is anchored to your audit chain with the regulation that triggered it.

To raise exceptions instead of returning block dicts:

```python
from phronedge import PhronEdge, ToolBlocked

pe = PhronEdge(agent_id="claims-investigator", raise_on_block=True)

@pe.govern("claim_lookup", action="read", jurisdiction="CN")
def claim_lookup_china(claim_id):
    return db.query(claim_id)

try:
    result = claim_lookup_china("CLM-001")
except ToolBlocked as e:
    print(e.reason)       # "Jurisdiction 'CN' not permitted..."
    print(e.checkpoint)   # "jurisdiction"
    print(e.regulation)   # "GDPR Art. 44-49"
    print(e.blocked)      # True
    print(e.retry)        # True
```

`ToolBlocked` is the primary exception. `GovernanceError` is the base class and is also importable for broad catches.

## What an allow looks like

Allowed calls return the function result normally. The Observer shows:

| Field | Value |
|-------|-------|
| Event | `TOOL_CALL_ALLOWED` |
| Agent | `claims-investigator` |
| Tool | `claim_lookup` |
| Action | `read` |
| Checkpoint | All 7 passed |
| Hash | `a7f3b2c9...` |
| Prev Hash | `d1e4f5a6...` |
| Regulation | `GDPR Art. 5(1)(f), EU AI Act Art. 9` |

Every event is SHA-256 hashed and chained to the previous event. Tamper one and the chain breaks.

## Sign a policy

Before your tools can be governed, you need a signed policy. Three paths, same outcome.

### Console (recommended for CISOs and platform teams)

Go to [phronedge.com/brain](https://phronedge.com/brain), open **Policy Builder**, walk through 3 steps:

1. **Organization**: HQ jurisdiction, industry, data types, residency, deployment jurisdictions
2. **Agents and Tools**: Each agent gets a tier (T0 to T3), data clearance, behavioral baseline, token budget. Each tool gets a data class, minimum tier, jurisdictions, permissions, and rate limits.
3. **Organization Policy**: Tenant-wide ceiling (allowed models, global deny patterns, auto-quarantine triggers, escalation rules)

Click **Sign and Deploy**. The Brain evaluates against all applicable regulatory frameworks for your jurisdiction and industry. If compliant, credentials are issued and events anchored. Open the **Architecture** view to see your signed policy as JSON, YAML, and OPA Rego.

### CLI (recommended for CI/CD)

```bash
phronedge policy build policy.yaml     # preview only, no credentials issued
phronedge policy deploy policy.yaml    # sign and issue credentials
phronedge policy status                # show registered agents and tools
```

### API (for automation)

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
        "id": "claims-investigator",
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
    "deploy": True,
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
print(result["credentials_issued"])               # [{"agent_id": "claims-investigator", ...}]
```

**Important:** Set `"deploy": true` to sign and issue credentials. Without it, the policy is signed for review only. Credentials are not persisted. Tool calls will fail with "No phronedge_signature in credential."

## Required tool fields

Every tool must declare these fields. Missing fields are rejected at policy build time. No silent defaults.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | str | yes | Must match `@pe.govern("id")` in your code |
| `description` | str | yes | What this tool does |
| `type` | str | yes | `sdk`, `api`, or `mcp` |
| `data_classification` | str | yes | One of `PUB`, `INT`, `PII`, `PHI`, `SPC`, `FIN`, `CON`, `RST` |
| `permissions` | list | yes | Actions allowed: `read`, `write`, `delete`, `execute` |
| `jurisdictions` | list | yes | ISO alpha-2 codes where this tool may be called |
| `deny_patterns` | list | no | Input patterns to block (e.g. `["DROP", "DELETE"]`) |
| `max_per_day` | int | no | Maximum calls per day |
| `requires_human_approval` | bool | no | Block until human approval |

A tool with `data_classification: "PLI"` (typo) is rejected. A tool with no `jurisdictions` is rejected. Fail-closed by design.

## Export your policy as code

After signing, export your policy as OPA Rego, YAML, or JSON:

```bash
phronedge export rego --agent claims-investigator -o policy.rego
phronedge export yaml --agent claims-investigator -o policy.yaml
phronedge export json --agent claims-investigator -o policy.json
```

Or open **Architecture** view in the Console and switch between the JSON, YAML, and OPA tabs.

The Rego export is a complete OPA policy bundle with 9 checkpoint rules, denial reasons, and regulatory citations. Drop it into any OPA runtime for independent enforcement outside PhronEdge.

## Verify your setup

```bash
phronedge verify --agent claims-investigator
```

Output:

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

## Scan your code

Confirm all tools in your codebase are governed:

```bash
phronedge scan my_agent.py
```

Output:

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

Use `--strict` in CI to fail the build on ungoverned tools:

```bash
phronedge scan src/agents/*.py --strict
```

## Independent verification

Every signed policy can be verified by anyone, using only the public key. No PhronEdge involvement required. A regulator can run this script against your credential.

```python
import requests, json
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.exceptions import InvalidSignature

# 1. Fetch your tenant's public keys (no auth required)
tenant_id = "tn_your_tenant_id"
r = requests.get(f"https://api.phronedge.com/.well-known/phronedge/{tenant_id}/keys.json")
keys = r.json()["keys"]

# 2. Pick the key used to sign your credential
key_id = credential["phronedge_signature"]["key_id"]  # e.g. "v2"
active_key = next(k for k in keys if k["kid"] == key_id)
pub_key = serialization.load_pem_public_key(active_key["pem"].encode())

# 3. Reconstruct the signed payload
sig_hex = credential["phronedge_signature"]["value"]
payload = {k: v for k, v in credential.items() if k not in ("phronedge_signature", "anchor_hash", "anchor_tx")}
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

# 4. Verify
try:
    pub_key.verify(bytes.fromhex(sig_hex), canonical, ec.ECDSA(hashes.SHA256()))
    print("Signature valid. Policy is authentic.")
except InvalidSignature:
    print("Signature invalid. Policy has been tampered with.")
```

The math proves authenticity. Zero trust in PhronEdge required.

## Full runnable example

This script signs a policy, deploys credentials, runs governed tools, tests blocks, and verifies the chain. Copy it, set your API key, run it.

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

# 1. Sign and deploy policy (credentials issued)
log.info("Signing and deploying policy...")
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
    "deploy": True,
}
r = requests.post(f"{API}/governance/build", headers=H, json=policy, timeout=30)
log.info("Status: %s", r.json().get("status"))

# 2. Govern and call
from phronedge import PhronEdge, ToolBlocked

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
except ToolBlocked as e:
    log.info("BLOCKED: %s (checkpoint=%s regulation=%s)", e.reason, e.checkpoint, e.regulation)

# 4. Test block: SQL injection pattern
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def bad_inject(query):
    return "SHOULD NOT RUN"

try:
    bad_inject("DROP TABLE claims")
except ToolBlocked as e:
    log.info("BLOCKED: %s", e.reason)

log.info("Done. Check phronedge.com/brain for the audit trail.")
```

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
python quickstart_e2e.py
```

Expected output:

```
08:30:00 INFO  Signing and deploying policy...
08:30:01 INFO  Status: compliant
08:30:03 INFO  ALLOWED: {"id": "CLM-001", "status": "OPEN", "amount": 12500}
08:30:04 INFO  BLOCKED: Jurisdiction 'CN' not permitted... (checkpoint=jurisdiction regulation=GDPR Art. 44-49)
08:30:05 INFO  BLOCKED: Global deny pattern 'DROP TABLE' matched.
08:30:05 INFO  Done. Check phronedge.com/brain for the audit trail.
```

## Next steps

- [SDK reference](/docs/sdk). Every parameter, every method, every error
- [CLI reference](/docs/cli). All 14 commands
- [REST API reference](/docs/api). Every endpoint with request and response examples
- [Console guide](/docs/console). Policy Builder, Observer, Architecture, Audit Log, Settings
- [Framework guides](/docs/frameworks). LangGraph, CrewAI, Google ADK, OpenAI Agents, LlamaIndex
- [Multi-agent governance](/docs/multi-agent). Delegation, sub-agents, chain governance
- [Enterprise deployment](/docs/enterprise-deployment). Deploy on your infrastructure with your KMS
- [Signing and verification](/docs/signing-verification). ECDSA signatures, key rotation, independent verification
- [Compliance matrix](/docs/compliance-matrix). Regulation to control to evidence
- [Threat model](/docs/threat-model). What PhronEdge protects against and what it does not
- [Deployment runbook](/docs/deployment-runbook). Day 1 through production readiness
