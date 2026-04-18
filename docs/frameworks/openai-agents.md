# OpenAI Agents

Govern OpenAI Agents SDK with PhronEdge. Every tool call passes through 7 checkpoints before execution. The agent sees a normal tool. The governance is invisible.

## Install

```bash
pip install phronedge openai-agents
```

## Basic integration

PhronEdge goes on the inside, OpenAI's `@function_tool` goes on the outside.

```python
import json
from phronedge import PhronEdge
from agents import Agent, Runner, function_tool

pe = PhronEdge(agent_id="claims-investigator")

@function_tool
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID like CLM-2026-001."""
    return json.dumps({"claim_id": claim_id, "status": "OPEN", "amount": 12500})

@function_tool
@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query: str) -> str:
    """Search patient records by name."""
    return json.dumps([{"id": "PAT-001", "name": query, "dob": "1978-03-15"}])

agent = Agent(
    name="Claims Investigator",
    instructions="Investigate insurance claims. Look up claims and find patients.",
    tools=[claim_lookup, patient_search],
)

import asyncio
result = asyncio.run(Runner.run(agent, "Look up claim CLM-2026-001 and find the patient"))
print(result.final_output)
```

The agent calls tools normally. PhronEdge intercepts each call, validates the credential, and either allows or blocks. The agent never knows governance is there.

## Decorator order

PhronEdge must be the inner decorator. The framework decorator goes on the outside.

```python
# Correct: @function_tool outside, @pe.govern inside
@function_tool
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Search claims."""
    ...

# Wrong: @pe.govern outside
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
@function_tool
def claim_lookup(claim_id: str) -> str:
    """Search claims."""
    ...
```

## Multi-tool agent

An agent with multiple tools, each with different permissions:

```python
import json
from phronedge import PhronEdge
from agents import Agent, Runner, function_tool

pe = PhronEdge(agent_id="claims-investigator")

@function_tool
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up a claim by ID. Read-only, Germany only."""
    return json.dumps(claims_db.get(claim_id))

@function_tool
@pe.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> str:
    """Run fraud detection on a claim. Execute permission required."""
    return json.dumps(fraud_engine.analyze(claim_id))

@function_tool
@pe.govern("approve_payout", action="write", jurisdiction="DE")
def approve_payout(claim_id: str, amount: float) -> str:
    """Approve a claim payout. Write permission required."""
    return json.dumps(payments.process(claim_id, amount))

agent = Agent(
    name="Claims Investigator",
    instructions="Investigate claims, scan for fraud, and approve valid ones.",
    tools=[claim_lookup, fraud_scan, approve_payout],
)
```

## Handling blocks

Use `raise_on_block=False` (the default) for OpenAI Agents. When a tool is blocked, PhronEdge returns a JSON string with the block reason. The model sees this and adapts.

```python
pe = PhronEdge(agent_id="claims-investigator")

@function_tool
@pe.govern("restricted_tool", action="write", jurisdiction="DE")
def restricted_tool(data: str) -> str:
    """Tool that requires write permission."""
    return process(data)

# If blocked, the model receives:
# {"blocked": true, "reason": "Action 'write' not permitted...", "checkpoint": "judge"}
# The model can report the limitation or try a different approach.
```

## Full runnable example

Copy this script, set your keys, and run it. It signs a policy, creates an OpenAI agent with governed tools, runs it, and shows the results.

```python
"""
PhronEdge + OpenAI Agents: governed agent from zero.
pip install phronedge openai-agents requests
"""
import os, json, logging, asyncio, requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phronedge.openai")

API = os.environ.get("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")
KEY = os.environ["PHRONEDGE_API_KEY"]
H = {"X-PhronEdge-Key": KEY, "Content-Type": "application/json"}

# 1. Sign policy
log.info("Signing policy...")
policy = {
    "organization": {
        "name": "OpenAI Agents Test",
        "jurisdiction": "DE",
        "industry": "IN",
        "data_types": ["PUB", "PII"],
        "data_residency": ["DE"],
        "deployment_jurisdictions": ["DE"],
    },
    "agents": [{
        "id": "openai-agent",
        "purpose": "Investigate insurance claims using OpenAI Agents",
        "model": "gpt-4o",
        "tier": "T2",
        "role": "standalone",
        "data_classifications": ["PUB", "PII"],
        "tools": ["claim_lookup", "patient_search"],
        "host_jurisdiction": "DE",
        "serving_jurisdictions": ["DE"],
    }],
    "tools": [
        {
            "id": "claim_lookup",
            "description": "Search insurance claims by ID",
            "type": "sdk",
            "data_classification": "PII",
            "permissions": ["read"],
            "jurisdictions": ["DE"],
            "deny_patterns": ["DROP", "DELETE"],
        },
        {
            "id": "patient_search",
            "description": "Search patient records by name",
            "type": "sdk",
            "data_classification": "PII",
            "permissions": ["read"],
            "jurisdictions": ["DE"],
        },
    ],
}
policy["deploy"] = True

r = requests.post(f"{API}/governance/build", headers=H, json=policy, timeout=30)
result = r.json()
log.info("Policy: %s | Controls: %s/%s",
         result.get("status"),
         result.get("signed_artifact", {}).get("controls_met"),
         result.get("signed_artifact", {}).get("controls_required"))

# 2. Create governed tools
from phronedge import PhronEdge
from agents import Agent, Runner, function_tool

pe = PhronEdge(agent_id="openai-agent")

@function_tool
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID like CLM-2026-001."""
    claims = {
        "CLM-2026-001": {"status": "OPEN", "amount": 12500, "patient": "Hans Mueller"},
        "CLM-2026-002": {"status": "UNDER_REVIEW", "amount": 45000, "patient": "Anna Schmidt"},
    }
    return json.dumps(claims.get(claim_id, {"error": "not found"}))

@function_tool
@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query: str) -> str:
    """Search patient records by name."""
    patients = [
        {"id": "PAT-001", "name": "Hans Mueller", "dob": "1978-03-15"},
        {"id": "PAT-002", "name": "Anna Schmidt", "dob": "1985-11-22"},
    ]
    results = [p for p in patients if query.lower() in p["name"].lower()]
    return json.dumps(results if results else [{"error": "not found"}])

# 3. Build and run agent
log.info("Creating OpenAI agent...")
agent = Agent(
    name="Claims Investigator",
    instructions="Investigate insurance claims. Look up claims and find patients.",
    tools=[claim_lookup, patient_search],
)

log.info("Running agent...")
result = asyncio.run(
    Runner.run(agent, "Look up claim CLM-2026-001 and find the patient details")
)

log.info("Agent response:\n%s", result.final_output)
log.info("Done. Check phronedge.com/brain for the audit trail.")
```

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
export OPENAI_API_KEY=sk_your_openai_key
python openai_agents_e2e.py
```

Expected output:

```
08:30:00 INFO  Signing policy...
08:30:01 INFO  Policy: compliant | Controls: 30/30
08:30:01 INFO  Creating OpenAI agent...
08:30:01 INFO  Running agent...
08:30:05 INFO  Agent response:
Claim CLM-2026-001 is OPEN for $12,500. The patient is Hans Mueller (PAT-001), born 1978-03-15.
08:30:05 INFO  Done. Check phronedge.com/brain for the audit trail.
```

Every tool call was governed. Every decision was logged. The agent never knew.

## Next steps

- [LangGraph guide](/docs/frameworks/langgraph): Govern LangGraph agents and StateGraphs
- [CrewAI guide](/docs/frameworks/crewai): Multi-agent crews with governed tools
- [Google ADK guide](/docs/frameworks/adk): Govern ADK agents
- [LlamaIndex guide](/docs/frameworks/llamaindex): Govern LlamaIndex ReAct agents
- [SDK reference](/docs/sdk): Every parameter, method, and error
