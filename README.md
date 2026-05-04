# PhronEdge

Constitutional AI governance for every agent, every tool, every call.

```bash
pip install phronedge
```

## What it does

PhronEdge wraps your AI agent tool calls with 7 governance checkpoints. Under 50ms. Your data stays in your runtime. Works with any framework.

```python
from phronedge import PhronEdge

pe = PhronEdge(agent_id="fraud-analyst")

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID."""
    return db.query(claim_id)

# This call passes through 7 checkpoints before executing
result = claim_lookup("CLM-2026-001")
```

## Frameworks

Works with every major agent framework. One decorator. Same pattern.

| Framework | Tested | Decorator order |
|-----------|--------|-----------------|
| LangGraph | Yes | `@tool` outside, `@pe.govern` inside |
| CrewAI | Yes | `@tool("name")` outside, `@pe.govern` inside |
| OpenAI Agents | Yes | `@function_tool` outside, `@pe.govern` inside |
| LlamaIndex | Yes | `@pe.govern` only (no framework decorator needed) |
| Google ADK | Yes | `@pe.govern` only (no framework decorator needed) |
| AutoGen | Yes | `@pe.govern` only (no framework decorator needed) |

## Multi-agent

One API key. Multiple agents. Each with independent credentials, tools, and clearances.

```python
pe_fraud = PhronEdge(agent_id="fraud-analyst")
pe_kyc = PhronEdge(agent_id="agt-kyc-orch-v1")
pe_settle = PhronEdge(agent_id="agt-settle-v1")
```

## 7 checkpoints

Every governed tool call passes through:

1. **Credential validation** : ML-DSA-65 signature verified
2. **Tool permission** : Is this tool in the signed credential?
3. **Data classification** : Does agent clearance match the data level?
4. **PII detection** : Input scanned for personal data
5. **Jurisdiction check** : Is this jurisdiction allowed for this tool?
6. **Behavioral analysis** : Is this call within normal baseline?
7. **Output constraints** : Response scanned before return

## CLI

```bash
# ─────────────────────────────────────────────
# SETUP (prereqs)
# ─────────────────────────────────────────────
pip install phronedge
export PHRONEDGE_API_KEY=pe_live_your_key_here
# Optional: override for enterprise self-hosted
# export PHRONEDGE_GATEWAY_URL=https://governance.internal.yourcompany.com/api/v1

# ─────────────────────────────────────────────
# PRE-FLIGHT (existing in 2.3.0)
# ─────────────────────────────────────────────
phronedge verify
phronedge verify --agent fraud-analyst

# ─────────────────────────────────────────────
# POLICY LIFECYCLE (new in 2.4.0)
# ─────────────────────────────────────────────
phronedge policy build policy.yaml
phronedge policy deploy policy.yaml
phronedge policy status

# ─────────────────────────────────────────────
# EXPORT (existing in 2.3.0)
# ─────────────────────────────────────────────
phronedge export rego -o policy.rego
phronedge export yaml -o gov.yaml
phronedge export json -o policy.json
# With agent scope
phronedge export rego --agent fraud-analyst -o fraud.rego

# ─────────────────────────────────────────────
# AGENT LIFECYCLE (new in 2.4.0)
# ─────────────────────────────────────────────
phronedge agent list
phronedge agent quarantine fraud-analyst "suspicious behavior detected"
phronedge agent reinstate fraud-analyst "investigation cleared"

# ─────────────────────────────────────────────
# CHAIN & AUDIT (new in 2.4.0)
# ─────────────────────────────────────────────
phronedge chain verify
phronedge chain events --limit 20

# ─────────────────────────────────────────────
# CODE QUALITY (existing in 2.3.0)
# ─────────────────────────────────────────────
phronedge scan my_agent.py
phronedge scan my_agent.py --strict
```

## Enterprise

Deploy PhronEdge on your own infrastructure. Same SDK. Same `@pe.govern()`. One env var change.

```bash
# SaaS (default)
export PHRONEDGE_API_KEY=pe_live_xxx

# Enterprise (your k8s, your KMS, your Postgres)
export PHRONEDGE_API_KEY=pe_live_xxx
export PHRONEDGE_GATEWAY_URL=https://governance.internal.bank.com/api/v1
```

Per-tenant ML-DSA-65 signing keys. Independent verification via public key endpoint. Multi-cloud KMS (AWS, GCP, Azure). Storage abstraction (Firestore or Postgres). Helm chart for k8s. Docker, ECS, Cloud Run. Your developer's code doesn't change.

196 jurisdictions. 30 controls. SHA-256 hash-chained audit trail. Tamper-proof. Mathematically verifiable.

## Documentation

- [Quickstart](https://phronedge.com/docs/quickstart)
- [LangGraph](https://phronedge.com/docs/frameworks/langgraph)
- [CrewAI](https://phronedge.com/docs/frameworks/crewai)
- [Google ADK](https://phronedge.com/docs/frameworks/adk)
- [OpenAI Agents](https://phronedge.com/docs/frameworks/openai-agents)
- [LlamaIndex](https://phronedge.com/docs/frameworks/llamaindex)
- [AutoGen](https://phronedge.com/docs/frameworks/autogen)
- [SDK Reference](https://phronedge.com/docs/sdk)
- [CLI Reference](https://phronedge.com/docs/cli)
- [API Reference](https://phronedge.com/docs/api)
- [Multi-Agent](https://phronedge.com/docs/multi-agent)
- [Console Guide](https://phronedge.com/docs/console)

## License

MIT
