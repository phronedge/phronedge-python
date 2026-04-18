# LangGraph

Govern LangGraph agents with PhronEdge. Every tool call passes through 7 checkpoints before execution. The agent sees a normal tool. The governance is invisible.

## Install

```bash
pip install phronedge langgraph langchain-openai
```

## Basic integration

PhronEdge goes on the inside, LangGraph's `@tool` goes on the outside. The decorator order matters.

```python
from phronedge import PhronEdge
from langchain_core.tools import tool
from langchain.agents import create_react_agent
from langchain_openai import ChatOpenAI

pe = PhronEdge(agent_id="claims-investigator")

@tool
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID."""
    return json.dumps({"claim_id": claim_id, "status": "OPEN", "amount": 12500})

@tool
@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query: str) -> str:
    """Search patient records by name."""
    return json.dumps([{"id": "PAT-001", "name": query, "dob": "1978-03-15"}])

llm = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, [claim_lookup, patient_search])

result = agent.invoke({"messages": [("user", "Look up claim CLM-2026-001 and find the patient")]})
```

The agent calls `claim_lookup` and `patient_search` normally. PhronEdge intercepts each call, validates the credential, and either allows or blocks it. The agent never knows governance is there.

## Decorator order

PhronEdge must be the inner decorator (closest to the function). The framework decorator goes on the outside.

```python
# Correct: @tool outside, @pe.govern inside
@tool
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Search claims."""
    ...

# Wrong: @pe.govern outside
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
@tool
def claim_lookup(claim_id: str) -> str:
    """Search claims."""
    ...
```

## Multi-tool agent

An agent with multiple tools, each with different permissions and jurisdictions:

```python
from phronedge import PhronEdge
from langchain_core.tools import tool
from langchain.agents import create_react_agent
from langchain_openai import ChatOpenAI

pe = PhronEdge(agent_id="claims-investigator")

@tool
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up a claim by ID. Read-only, Germany only."""
    return claims_db.get(claim_id)

@tool
@pe.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> str:
    """Run fraud detection on a claim. Execute permission required."""
    return fraud_engine.analyze(claim_id)

@tool
@pe.govern("approve_payout", action="write", jurisdiction="DE")
def approve_payout(claim_id: str, amount: float) -> str:
    """Approve a claim payout. Write permission required."""
    return payments.process(claim_id, amount)

llm = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, [claim_lookup, fraud_scan, approve_payout])

# The agent can look up claims and scan for fraud.
# If it tries to approve a payout but lacks write clearance,
# PhronEdge blocks the call and the agent gets a structured denial.
result = agent.invoke({
    "messages": [("user", "Investigate claim CLM-2026-001 and approve if clean")]
})
```

## Multi-agent graph

A LangGraph StateGraph with multiple agents, each governed independently:

```python
import json
from typing import TypedDict, Annotated
from phronedge import PhronEdge
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

# Each agent gets its own PhronEdge instance with its own credential
pe_intake = PhronEdge(agent_id="agt-intake-v1")
pe_fraud = PhronEdge(agent_id="agt-fraud-v1")
pe_settle = PhronEdge(agent_id="agt-settle-v1")

@tool
@pe_intake.govern("claim_lookup", action="read", jurisdiction="DE")
def intake_lookup(claim_id: str) -> str:
    """Look up incoming claim details."""
    return json.dumps({"claim_id": claim_id, "status": "NEW", "amount": 25000})

@tool
@pe_fraud.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_check(claim_id: str) -> str:
    """Scan claim for fraud indicators."""
    return json.dumps({"claim_id": claim_id, "risk": "LOW", "score": 12})

@tool
@pe_settle.govern("payment_process", action="write", jurisdiction="DE")
def process_payment(claim_id: str) -> str:
    """Process approved settlement."""
    return json.dumps({"claim_id": claim_id, "status": "PAID", "amount": 25000})


class ClaimsState(TypedDict):
    claim_id: str
    intake_result: str
    fraud_result: str
    settlement_result: str


def intake_node(state: ClaimsState) -> ClaimsState:
    result = intake_lookup.invoke(state["claim_id"])
    return {"intake_result": result}

def fraud_node(state: ClaimsState) -> ClaimsState:
    result = fraud_check.invoke(state["claim_id"])
    return {"fraud_result": result}

def settlement_node(state: ClaimsState) -> ClaimsState:
    result = process_payment.invoke(state["claim_id"])
    return {"settlement_result": result}


graph = StateGraph(ClaimsState)
graph.add_node("intake", intake_node)
graph.add_node("fraud", fraud_node)
graph.add_node("settlement", settlement_node)
graph.set_entry_point("intake")
graph.add_edge("intake", "fraud")
graph.add_edge("fraud", "settlement")
graph.add_edge("settlement", END)

app = graph.compile()
result = app.invoke({"claim_id": "CLM-2026-001"})
```

Each node uses a different `PhronEdge` instance. The intake agent can only read. The fraud agent can execute scans. The settlement agent can write payments. If any agent tries to exceed its clearance, PhronEdge blocks that specific call without stopping the rest of the graph.

## Handling blocks

When PhronEdge blocks a tool call, the behavior depends on `raise_on_block`:

**Default (raise_on_block=False):** The tool returns a JSON string with the block reason. The LLM sees this and can decide what to do next. This is usually what you want for agents because it lets them adapt.

```python
pe = PhronEdge(agent_id="claims-investigator")

@tool
@pe.govern("restricted_tool", action="write", jurisdiction="DE")
def restricted_tool(data: str) -> str:
    """Tool that requires write permission."""
    return process(data)

# If blocked, the LLM receives:
# {"blocked": true, "reason": "Action 'write' not permitted...", "checkpoint": "judge"}
# The LLM can then try a different approach or report the limitation.
```

**With raise_on_block=True:** The tool raises a `ToolBlocked`. LangGraph catches it as a tool error.

```python
pe = PhronEdge(agent_id="claims-investigator", raise_on_block=True)

@tool
@pe.govern("restricted_tool", action="write", jurisdiction="DE")
def restricted_tool(data: str) -> str:
    """Tool that requires write permission."""
    return process(data)

# If blocked, raises ToolBlocked. LangGraph handles it as a tool error.
```

## Full runnable example

Copy this script, set your API key, and run it. It signs a policy, creates a LangGraph agent with governed tools, runs it, and shows the results.

```python
"""
PhronEdge + LangGraph: governed agent from zero.
pip install phronedge langgraph langchain-openai requests
"""
import os, json, logging, requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phronedge.langgraph")

API = os.environ.get("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")
KEY = os.environ["PHRONEDGE_API_KEY"]
H = {"X-PhronEdge-Key": KEY, "Content-Type": "application/json"}

# 1. Sign policy with two tools
log.info("Signing policy...")
policy = {
    "organization": {
        "name": "LangGraph Test",
        "jurisdiction": "DE",
        "industry": "IN",
        "data_types": ["PUB", "PII"],
        "data_residency": ["DE"],
        "deployment_jurisdictions": ["DE"],
    },
    "agents": [{
        "id": "langgraph-agent",
        "purpose": "Investigate insurance claims using LangGraph",
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
from langchain_core.tools import tool
from langchain.agents import create_react_agent
from langchain_openai import ChatOpenAI

pe = PhronEdge(agent_id="langgraph-agent")

@tool
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID like CLM-2026-001."""
    claims = {
        "CLM-2026-001": {"status": "OPEN", "amount": 12500, "patient": "Hans Mueller"},
        "CLM-2026-002": {"status": "UNDER_REVIEW", "amount": 45000, "patient": "Anna Schmidt"},
    }
    return json.dumps(claims.get(claim_id, {"error": "not found"}))

@tool
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
log.info("Creating LangGraph agent...")
llm = ChatOpenAI(model="gpt-4o")
agent = create_react_agent(llm, [claim_lookup, patient_search])

log.info("Running agent...")
result = agent.invoke({
    "messages": [("user", "Look up claim CLM-2026-001 and find the patient details")]
})

# 4. Print result
final = result["messages"][-1].content
log.info("Agent response:\n%s", final)
log.info("Done. Check phronedge.com/brain for the audit trail.")
```

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
export OPENAI_API_KEY=sk-your-openai-key
python langgraph_e2e.py
```

Expected output:

```
08:30:00 INFO  Signing policy...
08:30:01 INFO  Policy: compliant | Controls: 30/30
08:30:01 INFO  Creating LangGraph agent...
08:30:01 INFO  Running agent...
08:30:05 INFO  Agent response:
Claim CLM-2026-001 is currently OPEN with an amount of $12,500.
The patient is Hans Mueller, born on 1978-03-15 (Patient ID: PAT-001).
08:30:05 INFO  Done. Check phronedge.com/brain for the audit trail.
```

Every tool call was governed. Every decision was logged. The agent never knew.

## Next steps

- [CrewAI guide](/docs/frameworks/crewai): Multi-agent crews with governed tools
- [Google ADK guide](/docs/frameworks/adk): Govern ADK agents
- [Multi-agent governance](/docs/multi-agent): Delegation chains and sub-agents
- [SDK reference](/docs/sdk): Every parameter, method, and error
