# Multi-Agent Governance

Govern multiple agents under the same tenant with independent credentials, tools, and clearances. One API key. Every agent isolated.

## One key, many agents

Create separate `PhronEdge` instances for each agent. Each gets its own credential with its own tools, jurisdictions, and data clearances.

```python
from phronedge import PhronEdge

pe_fraud = PhronEdge(agent_id="fraud-analyst")
pe_kyc = PhronEdge(agent_id="agt-kyc-orch-v1")
pe_settle = PhronEdge(agent_id="agt-settle-v1")
```

All three use the same `PHRONEDGE_API_KEY`. The `agent_id` tells the gateway which credential to fetch. Each credential is independently signed with ECDSA P-256.

## Agent tiers

| Tier | Role | Description |
|------|------|-------------|
| T1 | Sub-agent | Can only use assigned tools. Cannot delegate. Reports to parent |
| T2 | Standalone | Full agent with its own tools and clearance. Can operate independently |
| T3 | Orchestrator | Coordinates sub-agents. Can delegate tasks. Has oversight authority |

Set the tier when you sign the policy:

```python
"agents": [
    {"id": "agt-kyc-v1", "tier": "T1", "role": "sub_agent", ...},
    {"id": "fraud-analyst", "tier": "T2", "role": "standalone", ...},
    {"id": "agt-risk-orch-v1", "tier": "T3", "role": "orchestrator", ...},
]
```

## Tool isolation

Each agent can only use the tools assigned in its signed credential. If agent A tries to call a tool assigned to agent B, the gateway blocks it.

```python
pe_fraud = PhronEdge(agent_id="fraud-analyst")
pe_kyc = PhronEdge(agent_id="agt-kyc-v1")

# Fraud analyst has: risk_report, customer_lookup, transaction_review
@pe_fraud.govern("customer_lookup", action="read", jurisdiction="DE")
def fraud_customer_lookup(customer_id: str) -> dict:
    return customers.get(customer_id)  # allowed

# KYC agent has: id_verify, risk_score
@pe_kyc.govern("id_verify", action="read", jurisdiction="DE")
def kyc_verify(doc_id: str) -> dict:
    return idv.verify(doc_id)  # allowed

# This would be blocked: fraud analyst trying to use KYC tool
@pe_fraud.govern("id_verify", action="read", jurisdiction="DE")
def fraud_trying_kyc(doc_id: str) -> dict:
    return idv.verify(doc_id)  # BLOCKED: id_verify not in fraud-analyst's credential
```

## Delegation

An orchestrator (T3) can delegate to sub-agents (T1). Define this in the policy:

```python
"agents": [
    {
        "id": "agt-risk-orch-v1",
        "tier": "T3",
        "role": "orchestrator",
        "can_delegate_to": ["agt-kyc-v1", "agt-aml-v1", "agt-fraud-v1"],
        ...
    },
    {
        "id": "agt-kyc-v1",
        "tier": "T1",
        "role": "sub_agent",
        "can_delegate_to": [],
        ...
    },
]
```

The gateway enforces delegation rules. If an agent tries to delegate to one not in its `can_delegate_to` list, the call is blocked.

## Data classification isolation

Different agents can have different data clearances:

```python
"agents": [
    {
        "id": "public-agent",
        "data_classifications": ["PUB"],           # public data only
        ...
    },
    {
        "id": "internal-agent",
        "data_classifications": ["PUB", "INT"],     # public + internal
        ...
    },
    {
        "id": "pii-agent",
        "data_classifications": ["PUB", "INT", "PII"],  # can handle PII
        ...
    },
]
```

If a tool has `data_classification: "PII"` and the calling agent only has `["PUB"]` clearance, the gateway blocks the call.

## Jurisdiction isolation

Each agent can operate in different jurisdictions:

```python
"agents": [
    {
        "id": "eu-agent",
        "host_jurisdiction": "DE",
        "serving_jurisdictions": ["DE", "AT", "CH", "FR"],
        ...
    },
    {
        "id": "us-agent",
        "host_jurisdiction": "US",
        "serving_jurisdictions": ["US"],
        ...
    },
]
```

Tools also have jurisdiction lists. The gateway checks both the agent and tool jurisdictions.

## Framework examples

### LangGraph multi-agent

```python
from phronedge import PhronEdge
from langchain_core.tools import tool
from langchain.agents import create_react_agent
from langchain_openai import ChatOpenAI

pe_intake = PhronEdge(agent_id="agt-intake-v1")
pe_fraud = PhronEdge(agent_id="agt-fraud-v1")

@tool
@pe_intake.govern("claim_lookup", action="read", jurisdiction="DE")
def intake_lookup(claim_id: str) -> str:
    """Look up incoming claim."""
    return claims_db.get(claim_id)

@tool
@pe_fraud.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> str:
    """Scan for fraud."""
    return fraud_engine.analyze(claim_id)

llm = ChatOpenAI(model="gpt-4o")
intake_agent = create_react_agent(llm, [intake_lookup])
fraud_agent = create_react_agent(llm, [fraud_scan])
```

### CrewAI multi-agent

```python
from phronedge import PhronEdge
from crewai import Agent, Task, Crew
from crewai.tools import tool

pe_analyst = PhronEdge(agent_id="agt-fraud-v1")
pe_auditor = PhronEdge(agent_id="agt-settle-v1")

@tool("fraud_scan")
@pe_analyst.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> str:
    """Scan claim for fraud."""
    return fraud_engine.analyze(claim_id)

@tool("process_payment")
@pe_auditor.govern("payment_process", action="write", jurisdiction="DE")
def process_payment(claim_id: str) -> str:
    """Process settlement."""
    return payments.process(claim_id)

analyst = Agent(role="Fraud Analyst", tools=[fraud_scan], ...)
auditor = Agent(role="Settlement Auditor", tools=[process_payment], ...)
crew = Crew(agents=[analyst, auditor], tasks=[...])
```

### Google ADK sub-agents

```python
from phronedge import PhronEdge
from google.adk.agents import Agent

pe_intake = PhronEdge(agent_id="agt-intake-v1")
pe_fraud = PhronEdge(agent_id="agt-fraud-v1")

@pe_intake.govern("claim_lookup", action="read", jurisdiction="DE")
def intake_lookup(claim_id: str) -> dict:
    return claims_db.get(claim_id)

@pe_fraud.govern("fraud_scan", action="execute", jurisdiction="DE")
def fraud_scan(claim_id: str) -> dict:
    return fraud_engine.analyze(claim_id)

intake = Agent(name="intake", tools=[intake_lookup], ...)
fraud = Agent(name="fraud", tools=[fraud_scan], ...)
orchestrator = Agent(name="orchestrator", sub_agents=[intake, fraud], ...)
```

## Audit trail

Every tool call from every agent is logged to the same tenant audit chain. The Observer in the console shows:

- Which agent made each call
- Which tool was called
- Whether it was allowed or blocked
- Which checkpoint and regulation triggered a block
- The SHA-256 hash chain linking every event

```bash
phronedge verify --agent fraud-analyst
phronedge verify --agent agt-kyc-orch-v1
phronedge verify --agent agt-settle-v1
```

One key. Three agents. Three independent credentials. All audited to the same chain.
