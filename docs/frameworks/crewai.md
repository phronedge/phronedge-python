# CrewAI

Govern CrewAI agents with PhronEdge. Every tool call passes through 7 checkpoints before execution. The crew sees normal tools. The governance is invisible.

## Install

```bash
pip install phronedge crewai
```

## Basic integration

PhronEdge goes on the inside, CrewAI's `@tool` goes on the outside.

```python
import json
from phronedge import PhronEdge
from crewai import Agent, Task, Crew
from crewai.tools import tool

pe = PhronEdge(agent_id="claims-investigator")

@tool("claim_lookup")
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID like CLM-2026-001."""
    return json.dumps({"claim_id": claim_id, "status": "OPEN", "amount": 12500})

@tool("patient_search")
@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query: str) -> str:
    """Search patient records by name."""
    return json.dumps([{"id": "PAT-001", "name": query, "dob": "1978-03-15"}])

investigator = Agent(
    role="Claims Investigator",
    goal="Investigate insurance claims and report findings",
    backstory="Senior claims investigator. Every tool call is governed.",
    tools=[claim_lookup, patient_search],
    verbose=True,
)

task = Task(
    description="Look up claim CLM-2026-001 and find the patient. Summarize.",
    agent=investigator,
    expected_output="Claim details with patient information.",
)

crew = Crew(agents=[investigator], tasks=[task], verbose=True)
result = crew.kickoff()
print(result)
```

CrewAI's LLM decides which tools to call. PhronEdge validates each call before the function body executes. The agent never knows governance is there.

## Decorator order

PhronEdge must be the inner decorator. CrewAI's `@tool` goes on the outside.

```python
# Correct: @tool outside, @pe.govern inside
@tool("claim_lookup")
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Search claims."""
    ...

# Wrong: @pe.govern outside
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
@tool("claim_lookup")
def claim_lookup(claim_id: str) -> str:
    """Search claims."""
    ...
```

## Multi-agent crew

A crew with multiple agents, each governed independently with different clearances:

```python
import json
from phronedge import PhronEdge
from crewai import Agent, Task, Crew
from crewai.tools import tool

# Each agent gets its own PhronEdge instance
pe_analyst = PhronEdge(agent_id="agt-fraud-v1")
pe_auditor = PhronEdge(agent_id="agt-settle-v1")

@tool("fraud_scan")
@pe_analyst.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> str:
    """Run fraud detection on a claim."""
    return json.dumps({"claim_id": claim_id, "risk": "LOW", "score": 12})

@tool("claim_lookup")
@pe_analyst.govern("claim_lookup", action="read", jurisdiction="DE")
def analyst_claim_lookup(claim_id: str) -> str:
    """Look up claim for fraud analysis."""
    return json.dumps({"claim_id": claim_id, "status": "OPEN", "amount": 25000})

@tool("payment_process")
@pe_auditor.govern("payment_process", action="write", jurisdiction="DE")
def process_payment(claim_id: str) -> str:
    """Process approved settlement payment."""
    return json.dumps({"claim_id": claim_id, "status": "PAID", "amount": 25000})

@tool("policy_check")
@pe_auditor.govern("policy_check", action="read", jurisdiction="DE")
def check_policy(claim_id: str) -> str:
    """Verify policy coverage for claim."""
    return json.dumps({"claim_id": claim_id, "covered": True, "limit": 50000})

analyst = Agent(
    role="Fraud Analyst",
    goal="Analyze claims for fraud indicators",
    backstory="Senior fraud analyst. Can scan and lookup but cannot process payments.",
    tools=[fraud_scan, analyst_claim_lookup],
    verbose=True,
)

auditor = Agent(
    role="Settlement Auditor",
    goal="Verify coverage and process approved payments",
    backstory="Settlement auditor. Can check policies and process payments.",
    tools=[process_payment, check_policy],
    verbose=True,
)

task1 = Task(
    description="Analyze claim CLM-2026-001 for fraud. Report findings.",
    agent=analyst,
    expected_output="Fraud analysis with risk score.",
)

task2 = Task(
    description="If the fraud check is clean, verify coverage and process payment.",
    agent=auditor,
    expected_output="Payment confirmation or denial.",
)

crew = Crew(agents=[analyst, auditor], tasks=[task1, task2], verbose=True)
result = crew.kickoff()
print(result)
```

The fraud analyst can scan and lookup but cannot process payments. The settlement auditor can process payments but cannot run fraud scans. PhronEdge enforces this per agent, per tool, per call.

## Handling blocks in CrewAI

Use `raise_on_block=False` (the default) for CrewAI. When a tool is blocked, PhronEdge returns a JSON string explaining why. The LLM sees this and adapts.

```python
pe = PhronEdge(agent_id="claims-investigator")

@tool("restricted_tool")
@pe.govern("restricted_tool", action="write", jurisdiction="DE")
def restricted_tool(data: str) -> str:
    """Tool that requires write permission."""
    return process(data)

# If blocked, the LLM receives:
# {"blocked": true, "reason": "Action 'write' not permitted...", "checkpoint": "judge"}
# The LLM can report the limitation or try a different approach.
```

Do not use `raise_on_block=True` with CrewAI unless you want the entire crew to stop on a governance block.

## Full runnable example

Copy this script, set your API key, and run it. It signs a policy, creates a CrewAI crew with governed tools, runs it, and shows the results.

```python
"""
PhronEdge + CrewAI: governed crew from zero.
pip install phronedge crewai requests
"""
import os, json, logging, requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phronedge.crewai")

API = os.environ.get("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")
KEY = os.environ["PHRONEDGE_API_KEY"]
H = {"X-PhronEdge-Key": KEY, "Content-Type": "application/json"}

# 1. Sign policy
log.info("Signing policy...")
policy = {
    "organization": {
        "name": "CrewAI Test",
        "jurisdiction": "DE",
        "industry": "IN",
        "data_types": ["PUB", "PII"],
        "data_residency": ["DE"],
        "deployment_jurisdictions": ["DE"],
    },
    "agents": [{
        "id": "crew-investigator",
        "purpose": "Investigate insurance claims using CrewAI",
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
from crewai import Agent, Task, Crew
from crewai.tools import tool

pe = PhronEdge(agent_id="crew-investigator")

@tool("claim_lookup")
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup(claim_id: str) -> str:
    """Look up an insurance claim by ID like CLM-2026-001."""
    claims = {
        "CLM-2026-001": {"status": "OPEN", "amount": 12500, "patient": "Hans Mueller"},
        "CLM-2026-002": {"status": "UNDER_REVIEW", "amount": 45000, "patient": "Anna Schmidt"},
    }
    return json.dumps(claims.get(claim_id, {"error": "not found"}))

@tool("patient_search")
@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query: str) -> str:
    """Search patient records by name."""
    patients = [
        {"id": "PAT-001", "name": "Hans Mueller", "dob": "1978-03-15"},
        {"id": "PAT-002", "name": "Anna Schmidt", "dob": "1985-11-22"},
    ]
    results = [p for p in patients if query.lower() in p["name"].lower()]
    return json.dumps(results if results else [{"error": "not found"}])

# 3. Build and run crew
log.info("Creating CrewAI agent...")
investigator = Agent(
    role="Claims Investigator",
    goal="Investigate insurance claims and report findings",
    backstory="Senior investigator. Every tool call governed by PhronEdge.",
    tools=[claim_lookup, patient_search],
    verbose=True,
)

task = Task(
    description="Look up claim CLM-2026-001 and find the patient. Summarize findings.",
    agent=investigator,
    expected_output="Claim details with patient information.",
)

crew = Crew(agents=[investigator], tasks=[task], verbose=True)

log.info("Running crew...")
result = crew.kickoff()

log.info("Crew result:\n%s", result)
log.info("Done. Check phronedge.com/brain for the audit trail.")
```

```bash
export PHRONEDGE_API_KEY=pe_live_your_key_here
export OPENAI_API_KEY=sk-your-openai-key
python crewai_e2e.py
```

Expected output:

```
08:30:00 INFO  Signing policy...
08:30:01 INFO  Policy: compliant | Controls: 30/30
08:30:01 INFO  Creating CrewAI agent...
08:30:01 INFO  Running crew...

Tool: claim_lookup
Args: {'claim_id': 'CLM-2026-001'}
Output: {"status": "OPEN", "amount": 12500, "patient": "Hans Mueller"}

Tool: patient_search
Args: {'query': 'Hans Mueller'}
Output: [{"id": "PAT-001", "name": "Hans Mueller", "dob": "1978-03-15"}]

08:30:08 INFO  Crew result:
Claim CLM-2026-001 is OPEN for $12,500.
Patient: Hans Mueller (PAT-001), born 1978-03-15.
08:30:08 INFO  Done. Check phronedge.com/brain for the audit trail.
```

Every tool call was governed. Every decision was logged. The crew never knew.

## Next steps

- [LangGraph guide](/docs/frameworks/langgraph): Govern LangGraph agents and StateGraphs
- [Google ADK guide](/docs/frameworks/adk): Govern ADK agents
- [Multi-agent governance](/docs/multi-agent): Delegation chains and sub-agents
- [SDK reference](/docs/sdk): Every parameter, method, and error
