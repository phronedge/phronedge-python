# Google ADK

Govern Google Agent Development Kit (ADK) agents with PhronEdge. Every tool call passes through 7 checkpoints before execution. No framework decorator needed. Just `@pe.govern`.

## Install

```bash
pip install phronedge google-adk
```

## Basic integration

ADK tools are plain Python functions. Wrap them with `@pe.govern` and pass them to the Agent constructor.

```python
import json, asyncio
from phronedge import PhronEdge
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> dict:
    """Look up an insurance claim by ID."""
    return {"claim_id": claim_id, "status": "OPEN", "amount": 12500}

@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query: str) -> list:
    """Search patient records by name."""
    return [{"id": "PAT-001", "name": query, "dob": "1978-03-15"}]

agent = Agent(
    name="claims_investigator",
    model="gemini-2.0-flash",
    instruction="Investigate insurance claims. Look up claims and find patients.",
    tools=[claim_lookup, patient_search],
)

session_service = InMemorySessionService()
runner = Runner(agent=agent, app_name="claims", session_service=session_service)

async def main():
    session = await session_service.create_session(app_name="claims", user_id="adjuster_1")
    message = types.Content(role="user", parts=[types.Part(text="Look up claim CLM-2026-001 and find the patient")])
    async for event in runner.run_async(user_id="adjuster_1", session_id=session.id, new_message=message):
        if event.is_final_response():
            print(event.content.parts[0].text)

asyncio.run(main())
```

No `@tool` decorator needed. ADK accepts plain functions. PhronEdge intercepts at the function boundary. The agent never knows governance is there.

**Important:** ADK agent names must use underscores, not hyphens. Use `claims_investigator` not `claims-investigator`. The PhronEdge `agent_id` can still use hyphens since it refers to your credential, not the ADK agent name.

## Multi-tool agent

An agent with multiple tools, each with different permissions:

```python
from phronedge import PhronEdge
from google.adk.agents import Agent

pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> dict:
    """Look up a claim by ID. Read-only, Germany only."""
    return claims_db.get(claim_id)

@pe.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> dict:
    """Run fraud detection on a claim. Execute permission required."""
    return fraud_engine.analyze(claim_id)

@pe.govern("approve_payout", action="write", jurisdiction="DE")
def approve_payout(claim_id: str, amount: float) -> dict:
    """Approve a claim payout. Write permission required."""
    return payments.process(claim_id, amount)

agent = Agent(
    name="claims_investigator",
    model="gemini-2.0-flash",
    instruction="Investigate claims, scan for fraud, and approve valid ones.",
    tools=[claim_lookup, fraud_scan, approve_payout],
)
```

## Multi-agent with sub-agents

ADK supports sub-agents natively. Each sub-agent gets its own PhronEdge instance with its own credential.

```python
from phronedge import PhronEdge
from google.adk.agents import Agent

pe_intake = PhronEdge(agent_id="agt-intake-v1")
pe_fraud = PhronEdge(agent_id="agt-fraud-v1")
pe_settle = PhronEdge(agent_id="agt-settle-v1")

@pe_intake.govern("claim_lookup", action="read", jurisdiction="DE")
def intake_lookup(claim_id: str) -> dict:
    """Look up incoming claim details."""
    return {"claim_id": claim_id, "status": "NEW", "amount": 25000}

@pe_fraud.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_check(claim_id: str) -> dict:
    """Scan claim for fraud indicators."""
    return {"claim_id": claim_id, "risk": "LOW", "score": 12}

@pe_settle.govern("payment_process", action="write", jurisdiction="DE")
def process_payment(claim_id: str) -> dict:
    """Process approved settlement."""
    return {"claim_id": claim_id, "status": "PAID", "amount": 25000}

intake_agent = Agent(
    name="intake",
    model="gemini-2.0-flash",
    instruction="Look up incoming claims and extract details.",
    tools=[intake_lookup],
)

fraud_agent = Agent(
    name="fraud_analyst",
    model="gemini-2.0-flash",
    instruction="Analyze claims for fraud indicators.",
    tools=[fraud_check],
)

settlement_agent = Agent(
    name="settlement",
    model="gemini-2.0-flash",
    instruction="Process approved claim payments.",
    tools=[process_payment],
)

orchestrator = Agent(
    name="claims_orchestrator",
    model="gemini-2.0-flash",
    instruction="Coordinate claim processing. Use intake, fraud, and settlement agents.",
    sub_agents=[intake_agent, fraud_agent, settlement_agent],
)
```

Each sub-agent has its own credential. The intake agent can only read. The fraud agent can execute scans. The settlement agent can write payments. PhronEdge enforces this independently per agent.

## Handling blocks

Use `raise_on_block=False` (the default) for ADK agents. When a tool is blocked, PhronEdge returns a dictionary with the block reason. The Gemini model sees this and adapts.

```python
pe = PhronEdge(agent_id="claims-investigator")

@pe.govern("restricted_tool", action="write", jurisdiction="DE")
def restricted_tool(data: str) -> dict:
    """Tool that requires write permission."""
    return process(data)

# If blocked, Gemini receives:
# {"blocked": true, "reason": "Action 'write' not permitted...", "checkpoint": "judge"}
# The model can report the limitation or try a different approach.
```

## Full runnable example

Copy this script, set your keys, and run it. It signs a policy, creates an ADK agent with governed tools, runs it, and shows the results.

```python
"""
PhronEdge + Google ADK: governed agent from zero.
pip install phronedge google-adk requests
"""
import os, json, logging, asyncio, requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phronedge.adk")

API = os.environ.get("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")
KEY = os.environ["PHRONEDGE_API_KEY"]
H = {"X-PhronEdge-Key": KEY, "Content-Type": "application/json"}

# 1. Sign policy
log.info("Signing policy...")
policy = {
    "organization": {
        "name": "ADK Test",
        "jurisdiction": "DE",
        "industry": "IN",
        "data_types": ["PUB", "PII"],
        "data_residency": ["DE"],
        "deployment_jurisdictions": ["DE"],
    },
    "agents": [{
        "id": "adk-agent",
        "purpose": "Investigate insurance claims using Google ADK",
        "model": "gemini-2.0-flash",
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
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

pe = PhronEdge(agent_id="adk-agent")

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> dict:
    """Look up an insurance claim by ID like CLM-2026-001."""
    claims = {
        "CLM-2026-001": {"status": "OPEN", "amount": 12500, "patient": "Hans Mueller"},
        "CLM-2026-002": {"status": "UNDER_REVIEW", "amount": 45000, "patient": "Anna Schmidt"},
    }
    return claims.get(claim_id, {"error": "not found"})

@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query: str) -> list:
    """Search patient records by name."""
    patients = [
        {"id": "PAT-001", "name": "Hans Mueller", "dob": "1978-03-15"},
        {"id": "PAT-002", "name": "Anna Schmidt", "dob": "1985-11-22"},
    ]
    return [p for p in patients if query.lower() in p["name"].lower()] or [{"error": "not found"}]

# 3. Build and run agent
log.info("Creating ADK agent...")
agent = Agent(
    name="adk_agent",
    model="gemini-2.0-flash",
    instruction="Investigate insurance claims. Look up claims and find patients.",
    tools=[claim_lookup, patient_search],
)

session_service = InMemorySessionService()
runner = Runner(agent=agent, app_name="claims", session_service=session_service)

async def main():
    session = await session_service.create_session(app_name="claims", user_id="adjuster_1")
    message = types.Content(
        role="user",
        parts=[types.Part(text="Look up claim CLM-2026-001 and find the patient details")],
    )
    log.info("Running agent...")
    async for event in runner.run_async(user_id="adjuster_1", session_id=session.id, new_message=message):
        if event.is_final_response():
            log.info("Agent response:\n%s", event.content.parts[0].text)

    log.info("Done. Check phronedge.com/brain for the audit trail.")

asyncio.run(main())
```

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
export GOOGLE_API_KEY=your_gemini_key
python adk_e2e.py
```

Expected output:

```
08:30:00 INFO  Signing policy...
08:30:01 INFO  Policy: compliant | Controls: 30/30
08:30:01 INFO  Creating ADK agent...
08:30:01 INFO  Running agent...
08:30:05 INFO  Agent response:
Claim CLM-2026-001 is OPEN for $12,500. The patient is Hans Mueller (PAT-001), born 1978-03-15.
08:30:05 INFO  Done. Check phronedge.com/brain for the audit trail.
```

Every tool call was governed. Every decision was logged. The agent never knew.

## Next steps

- [LangGraph guide](/docs/frameworks/langgraph): Govern LangGraph agents and StateGraphs
- [CrewAI guide](/docs/frameworks/crewai): Multi-agent crews with governed tools
- [Multi-agent governance](/docs/multi-agent): Delegation chains and sub-agents
- [SDK reference](/docs/sdk): Every parameter, method, and error
