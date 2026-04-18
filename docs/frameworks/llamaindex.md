# LlamaIndex

Govern LlamaIndex agents with PhronEdge. Every tool call passes through 7 checkpoints before execution. The agent sees a normal tool. The governance is invisible.

## Install

```bash
pip install phronedge llama-index llama-index-llms-openai
```

## Basic integration

Wrap your functions with `@pe.govern`, then pass them directly to the ReActAgent. LlamaIndex auto-converts plain functions to tools.

```python
import json, asyncio
from phronedge import PhronEdge
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.workflow import Context
from llama_index.llms.openai import OpenAI

pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID like CLM-2026-001."""
    return json.dumps({"claim_id": claim_id, "status": "OPEN", "amount": 12500})

@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query: str) -> str:
    """Search patient records by name."""
    return json.dumps([{"id": "PAT-001", "name": query, "dob": "1978-03-15"}])

llm = OpenAI(model="gpt-4o")
agent = ReActAgent(tools=[claim_lookup, patient_search], llm=llm)
ctx = Context(agent)

async def main():
    response = await agent.run(user_msg="Look up claim CLM-2026-001 and find the patient", ctx=ctx)
    print(str(response))

asyncio.run(main())
```

No `@tool` decorator needed. LlamaIndex auto-converts plain functions. PhronEdge intercepts at the function boundary. The agent never knows governance is there.

## Using FunctionTool

If you prefer explicit tool definitions with `FunctionTool`, the same pattern works:

```python
from llama_index.core.tools import FunctionTool
from llama_index.core.agent.workflow import ReActAgent
from llama_index.llms.openai import OpenAI
from phronedge import PhronEdge

pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID."""
    return claims_db.get(claim_id)

tools = [FunctionTool.from_defaults(fn=claim_lookup)]
agent = ReActAgent(tools=tools, llm=OpenAI(model="gpt-4o"))
```

## Multi-tool agent

An agent with multiple tools, each with different permissions:

```python
from phronedge import PhronEdge
from llama_index.core.agent.workflow import ReActAgent
from llama_index.llms.openai import OpenAI

pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up a claim by ID. Read-only, Germany only."""
    return claims_db.get(claim_id)

@pe.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> str:
    """Run fraud detection on a claim. Execute permission required."""
    return fraud_engine.analyze(claim_id)

@pe.govern("approve_payout", action="write", jurisdiction="DE")
def approve_payout(claim_id: str, amount: float) -> str:
    """Approve a claim payout. Write permission required."""
    return payments.process(claim_id, amount)

agent = ReActAgent(
    tools=[claim_lookup, fraud_scan, approve_payout],
    llm=OpenAI(model="gpt-4o"),
)
```

## Multi-agent workflow

LlamaIndex supports multi-agent workflows with `AgentWorkflow`. Each agent gets its own PhronEdge instance.

```python
from phronedge import PhronEdge
from llama_index.core.agent.workflow import ReActAgent, AgentWorkflow
from llama_index.llms.openai import OpenAI

pe_fraud = PhronEdge(agent_id="agt-fraud-v1")
pe_settle = PhronEdge(agent_id="agt-settle-v1")

@pe_fraud.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> str:
    """Scan claim for fraud indicators."""
    return json.dumps({"claim_id": claim_id, "risk": "LOW", "score": 12})

@pe_settle.govern("payment_process", action="write", jurisdiction="DE")
def process_payment(claim_id: str) -> str:
    """Process approved settlement."""
    return json.dumps({"claim_id": claim_id, "status": "PAID", "amount": 25000})

llm = OpenAI(model="gpt-4o")

fraud_agent = ReActAgent(
    name="fraud_analyst",
    description="Analyzes claims for fraud indicators",
    tools=[fraud_scan],
    llm=llm,
)

settlement_agent = ReActAgent(
    name="settlement",
    description="Processes approved claim payments",
    tools=[process_payment],
    llm=llm,
)

workflow = AgentWorkflow(
    agents=[fraud_agent, settlement_agent],
    root_agent="fraud_analyst",
)

async def main():
    response = await workflow.run(user_msg="Analyze claim CLM-2026-001 for fraud and process if clean")
    print(str(response))
```

Each agent has its own credential. The fraud agent can execute scans but cannot process payments. The settlement agent can write payments but cannot run fraud scans.

## Handling blocks

Use `raise_on_block=False` (the default) for LlamaIndex agents. When a tool is blocked, PhronEdge returns a JSON string with the block reason. The ReAct loop sees this as an observation and adapts.

```python
pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("restricted_tool", action="write", jurisdiction="DE")
def restricted_tool(data: str) -> str:
    """Tool that requires write permission."""
    return process(data)

# If blocked, the ReAct loop receives as an observation:
# {"blocked": true, "reason": "Action 'write' not permitted...", "checkpoint": "judge"}
# The agent reasons about this and tries a different approach.
```

## Full runnable example

Copy this script, set your keys, and run it.

```python
"""
PhronEdge + LlamaIndex: governed agent from zero.
pip install phronedge llama-index llama-index-llms-openai requests
"""
import os, json, logging, asyncio, requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phronedge.llamaindex")

API = os.environ.get("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")
KEY = os.environ["PHRONEDGE_API_KEY"]
H = {"X-PhronEdge-Key": KEY, "Content-Type": "application/json"}

# 1. Sign policy
log.info("Signing policy...")
policy = {
    "organization": {
        "name": "LlamaIndex Test",
        "jurisdiction": "DE",
        "industry": "IN",
        "data_types": ["PUB", "PII"],
        "data_residency": ["DE"],
        "deployment_jurisdictions": ["DE"],
    },
    "agents": [{
        "id": "llama-agent",
        "purpose": "Investigate insurance claims using LlamaIndex",
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
from llama_index.core.agent.workflow import ReActAgent
from llama_index.core.workflow import Context
from llama_index.llms.openai import OpenAI

pe = PhronEdge(agent_id="llama-agent")

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID like CLM-2026-001."""
    claims = {
        "CLM-2026-001": {"status": "OPEN", "amount": 12500, "patient": "Hans Mueller"},
        "CLM-2026-002": {"status": "UNDER_REVIEW", "amount": 45000, "patient": "Anna Schmidt"},
    }
    return json.dumps(claims.get(claim_id, {"error": "not found"}))

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
log.info("Creating LlamaIndex agent...")
llm = OpenAI(model="gpt-4o")
agent = ReActAgent(tools=[claim_lookup, patient_search], llm=llm)
ctx = Context(agent)

async def main():
    log.info("Running agent...")
    response = await agent.run(
        user_msg="Look up claim CLM-2026-001 and find the patient details",
        ctx=ctx,
    )
    log.info("Agent response:\n%s", str(response))
    log.info("Done. Check phronedge.com/brain for the audit trail.")

asyncio.run(main())
```

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
export OPENAI_API_KEY=sk_your_openai_key
python llamaindex_e2e.py
```

Expected output:

```
08:30:00 INFO  Signing policy...
08:30:01 INFO  Policy: compliant | Controls: 30/30
08:30:01 INFO  Creating LlamaIndex agent...
08:30:01 INFO  Running agent...
08:30:06 INFO  Agent response:
The patient associated with claim CLM-2026-001 is Hans Mueller (PAT-001), born 1978-03-15.
08:30:06 INFO  Done. Check phronedge.com/brain for the audit trail.
```

Every tool call was governed. Every decision was logged. The agent never knew.

## Next steps

- [LangGraph guide](/docs/frameworks/langgraph): Govern LangGraph agents and StateGraphs
- [CrewAI guide](/docs/frameworks/crewai): Multi-agent crews with governed tools
- [Google ADK guide](/docs/frameworks/adk): Govern ADK agents
- [OpenAI Agents guide](/docs/frameworks/openai-agents): Govern OpenAI Agents
- [SDK reference](/docs/sdk): Every parameter, method, and error
