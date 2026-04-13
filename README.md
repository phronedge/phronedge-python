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

## Multi-agent

One API key. Multiple agents. Each with independent credentials, tools, and clearances.

```python
pe_fraud = PhronEdge(agent_id="fraud-analyst")
pe_kyc = PhronEdge(agent_id="agt-kyc-orch-v1")
pe_settle = PhronEdge(agent_id="agt-settle-v1")
```

## 7 checkpoints

Every governed tool call passes through:

1. **Credential validation** : ECDSA P-256 signature verified
2. **Tool permission** : Is this tool in the signed credential?
3. **Data classification** : Does agent clearance match the data level?
4. **PII detection** : Input scanned for personal data
5. **Jurisdiction check** : Is this jurisdiction allowed for this tool?
6. **Behavioral analysis** : Is this call within normal baseline?
7. **Output constraints** : Response scanned before return

## CLI

```bash
phronedge verify --agent fraud-analyst
phronedge export rego --agent fraud-analyst
phronedge scan my_agent.py
```

## Enterprise

Your data stays in your runtime. PhronEdge validates governance decisions, not your business data. Under 50ms at any scale. Export your policy as OPA Rego and run it independently.

199 jurisdictions. 30 controls. ECDSA P-256 signatures. SHA-256 hash-chained audit trail.

## Documentation

- [Quickstart](https://phronedge.com/docs/quickstart)
- [LangGraph](https://phronedge.com/docs/frameworks/langgraph)
- [CrewAI](https://phronedge.com/docs/frameworks/crewai)
- [Google ADK](https://phronedge.com/docs/frameworks/adk)
- [OpenAI Agents](https://phronedge.com/docs/frameworks/openai-agents)
- [LlamaIndex](https://phronedge.com/docs/frameworks/llamaindex)
- [SDK Reference](https://phronedge.com/docs/sdk)
- [CLI Reference](https://phronedge.com/docs/cli)
- [API Reference](https://phronedge.com/docs/api)
- [Multi-Agent](https://phronedge.com/docs/multi-agent)
- [Console Guide](https://phronedge.com/docs/console)

## License

MIT
