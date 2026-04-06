<div align="center">

<img src="https://img.shields.io/pypi/v/phronedge?style=for-the-badge&color=2350f0" />
<img src="https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge" />
<img src="https://img.shields.io/badge/EU%20AI%20Act-Compliant-22c55e?style=for-the-badge" />
<img src="https://img.shields.io/badge/GDPR-Enforced-22c55e?style=for-the-badge" />

# phronedge

**Runtime governance for AI agents.**

Every tool call checked. Every decision audited. Every regulation enforced.

[Playground](https://phronedge.com/playground) | [Documentation](https://docs.phronedge.com) | [Dashboard](https://phronedge.com/brain)

</div>

---

## The Problem

AI agents take actions. Actions have consequences. Right now there is no governance layer between your agent and everything it can touch.

Your agent can access data it was never authorized to see. Execute financial transactions without human approval. Leak sensitive information across jurisdictions. Be compromised through prompt injection. Have its credential tampered with at runtime.

And you will not know until a regulator asks you to prove it did not happen.

EU AI Act enforcement is live. GDPR fines reach 20M EUR or 4% of global revenue. The question is not whether your agent needs governance. The question is whether you can prove it has governance.

**An agent is an untrusted entity. Treat it like one.**

---

## The Solution

PhronEdge intercepts every tool call before it executes. Seven checkpoints. Every time. No exceptions.

```
Your agent calls a tool
        |
        v
CP1  Credential Validator    Is this agent who it claims to be? (ECDSA)
        |
CP2  PII / Injection Scan    Is there sensitive data or manipulation in the input?
        |
CP3  Jurisdiction Router     Is this action legally permitted? (196 countries)
        |
CP4  Behavioral Monitor      Is this agent behaving normally? (signed baseline)
        |
CP5  Data Classifier         What classification level is this data?
        |
CP6  Tool Permission         Is this tool in the agent's signed credential?
        |
CP7  Output Constraint       Is the response safe to return?
        |
        v
ALLOWED: your function executes normally
BLOCKED: reason + regulation citation returned, event anchored
```

---

## Install

```bash
pip install phronedge
```

Works with every Python package manager:

```bash
pip install phronedge
uv add phronedge
poetry add phronedge
pdm add phronedge
pipenv install phronedge
```

---

## Setup

One environment variable. Nothing else.

```bash
# .env
PHRONEDGE_API_KEY=pe_live_xxxxxxxxx
```

Get your API key at [phronedge.com/playground](https://phronedge.com/playground).

---

## Quick Start

```python
from phronedge import PhronEdge

pe = PhronEdge()

@pe.govern("lookup_claim")
def lookup_claim(claim_id: str) -> str:
    return db.query(claim_id)

result = lookup_claim("CLM-2026-001")
```

Three lines. Every call to `lookup_claim` now passes through 7 governance checkpoints. Your existing function does not change.

---

## What Governance Looks Like

Four scenarios. What your agent tries. What PhronEdge does.

**Clean call:**

```python
result = lookup_claim("CLM-2026-001")
# ALLOWED in 23ms
# Claim data returned to agent
# Audit: TOOL_CALL_ALLOWED, 7/7 checkpoints passed
```

**PII in input:**

```python
result = lookup_claim("SSN 123-45-6789")
# BLOCKED
# PII detected in function arguments (SSN pattern)
# Session escalated to PII_RESTRICTED
# Audit: PII_INPUT_DETECTED, GDPR Art. 9
```

**Tool not in credential:**

```python
result = access_medical_records("patient-123")
# BLOCKED
# medical_records not in agent's signed credential
# Function never executed. Data never touched.
# Audit: TOOL_CALL_BLOCKED, EU AI Act Art. 14
```

**Credential tampered at runtime:**

```python
# Attacker modifies credential at 2:00pm
# Agent makes next call at 2:01pm
result = lookup_claim("CLM-2026-001")
# ECDSA signature mismatch detected
# Vault restore runs automatically
# Call proceeds with restored credential
# You did nothing. PhronEdge fixed itself.
# Audit: VAULT_TAMPER_DETECTED + VAULT_CREDENTIAL_RESTORED
```

---

## Framework Examples

### LangChain / LangGraph

```python
from phronedge import PhronEdge
from langchain_core.tools import tool

pe = PhronEdge()

@pe.govern("lookup_claim")
def _governed_lookup(claim_id: str) -> str:
    return db.query(claim_id)

@tool
def lookup_claim(claim_id: str) -> str:
    """Look up an insurance claim by ID."""
    return _governed_lookup(claim_id)

agent = create_react_agent(llm, [lookup_claim])
```

### CrewAI

```python
from phronedge import PhronEdge
from crewai.tools import BaseTool

pe = PhronEdge()

@pe.govern("lookup_claim")
def _governed_lookup(claim_id: str) -> str:
    return db.query(claim_id)

class LookupClaimTool(BaseTool):
    name: str = "lookup_claim"
    description: str = "Look up an insurance claim"

    def _run(self, claim_id: str) -> str:
        return _governed_lookup(claim_id)

agent = Agent(role="Investigator", tools=[LookupClaimTool()])
```

### Google ADK

```python
from phronedge import PhronEdge
from google.adk.agents import Agent

pe = PhronEdge()

@pe.govern("lookup_claim")
def _governed_lookup(claim_id: str) -> str:
    return db.query(claim_id)

def lookup_claim(claim_id: str, tool_context) -> str:
    """Look up an insurance claim by ID."""
    return _governed_lookup(claim_id)

agent = Agent(name="investigator", model="gemini-2.0-flash", tools=[lookup_claim])
```

### OpenAI Function Calling

```python
from phronedge import PhronEdge
from openai import OpenAI

pe = PhronEdge()

@pe.govern("lookup_claim")
def lookup_claim(claim_id: str) -> str:
    return db.query(claim_id)

# Define tools as usual, call lookup_claim when the model requests it
# PhronEdge governs the execution automatically
```

### Pydantic AI

```python
from phronedge import PhronEdge
from pydantic_ai import Agent

pe = PhronEdge()

@pe.govern("lookup_claim")
def _governed_lookup(claim_id: str) -> str:
    return db.query(claim_id)

agent = Agent("openai:gpt-4o")

@agent.tool_plain
def lookup_claim(claim_id: str) -> str:
    """Look up an insurance claim."""
    return _governed_lookup(claim_id)
```

### Plain Python

```python
from phronedge import PhronEdge

pe = PhronEdge()

@pe.govern("send_payment")
def send_payment(claim_id: str, amount: float, currency: str) -> str:
    return payment_api.send(claim_id, amount, currency)

result = send_payment("CLM-001", 42500.0, "EUR")
# BLOCKED: requires human approval, checkpoint: human_oversight
```

---

## The Data Never Leaves

Your data stays in your environment. Governance metadata travels to PhronEdge. Nothing else.

```
What PhronEdge receives:              What PhronEdge never receives:
  Agent ID                              Your customer data
  Tool name                             Query results
  Input metadata (scanned, not stored)  Medical records
  Credential ID                         Financial data
                                        Internal service URLs
                                        Anything your tool returns
```

GDPR, HIPAA, and EU AI Act all require data to stay in the appropriate environment. PhronEdge is architecturally compliant by design. Not by configuration. By architecture.

---

## Constitutional Tiers

Every agent operates at a tier that defines its authority.

| Tier | Name | What it means |
|------|------|---------------|
| T0 | Advisory Only | Agent recommends. Human decides. No execution. |
| T1 | Human-in-the-Loop | Agent proposes. Waits for human approval. |
| T2 | Bounded Autonomy | Agent executes within scope. Escalates outside it. |
| T3 | Supervised Autonomy | Agent executes and logs. Human reviews after. |

High-value actions like financial transactions, sensitive data access, and irreversible operations are blocked at tiers below their required level. Automatically. Every time.

---

## Agent Lifecycle

Control any running agent in real time. No restart. No code change.

```python
# Quarantine: blocks all tool calls immediately
pe.quarantine("Suspicious pattern detected")

# Reinstate: resumes tool calls
pe.reinstate("Investigation complete")
```

Kill switch is available through the PhronEdge console only. Permanent agent termination is a critical operation that requires dashboard access at [phronedge.com/brain](https://phronedge.com/brain).

---

## The Audit Chain

Every event is cryptographically anchored. Every event links to the one before it. Tamper one event and the chain breaks.

```json
{
  "event_type":  "TOOL_CALL_BLOCKED",
  "agent_id":    "claims-investigator-v1",
  "tool":        "access_medical_records",
  "severity":    "HIGH",
  "regulation":  "EU AI Act Art. 14 Human Oversight",
  "checkpoint":  "data_classification",
  "policy_hash": "f107937d65017b17...",
  "hash":        "a3f2b1c4d5e6f7a8...",
  "prev_hash":   "9e8d7c6b5a4f3e2d...",
  "timestamp":   "2026-04-05T14:32:18.000Z"
}
```

Your regulator sees the complete governance history. Your auditor trusts the math.

---

## Error Handling

```python
from phronedge import PhronEdge, ToolBlocked, AgentTerminated

pe = PhronEdge(raise_on_block=True)

@pe.govern("send_payment")
def send_payment(claim_id, amount, currency):
    return payment_api.send(claim_id, amount, currency)

try:
    send_payment("CLM-001", 42500, "EUR")
except ToolBlocked as e:
    print(f"Blocked: {e} (checkpoint: {e.checkpoint})")
except AgentTerminated:
    print("Agent has been permanently killed")
```

---

## Pre-scan Text

Check text for PII or injection before sending to an LLM:

```python
pe = PhronEdge()
result = pe.scan("My SSN is 123-45-6789 and ignore previous instructions")
# {"pii_detected": true, "injection_detected": true, "patterns": ["SSN"]}
```

---

## Regulatory Coverage

PhronEdge maps every governance decision to the applicable regulation for your jurisdiction and industry.

**Cross-Industry:**

| Regulation | Coverage |
|------------|----------|
| EU AI Act 2024 | Risk classification, human oversight, transparency |
| GDPR (EU) 2016/679 | Data minimisation, transfer restrictions, Art. 9 special categories |
| Schrems II (C-311/18) | Cross-border data transfer enforcement |
| CCPA / CPRA | California consumer data protection |
| ISO 42001 | AI management system controls |
| NIST AI RMF | Govern, map, measure, manage |
| SOC 2 Type II | Security, availability, processing integrity |

**Financial Services:**

| Regulation | Coverage |
|------------|----------|
| FCA Handbook | UK financial conduct authority rules |
| MiFID II | Markets in Financial Instruments Directive |
| DORA | Digital Operational Resilience Act |
| PSD2 | Payment Services Directive |
| Basel III/IV | Risk management and capital requirements |
| MAR | Market Abuse Regulation |

**Healthcare:**

| Regulation | Coverage |
|------------|----------|
| HIPAA | Protected health information, access control |
| HITECH Act | Health information technology enforcement |
| FDA 21 CFR Part 11 | Electronic records and signatures |
| MDR (EU) 2017/745 | Medical Device Regulation |

**Insurance:**

| Regulation | Coverage |
|------------|----------|
| Solvency II | Insurance risk management |
| IDD | Insurance Distribution Directive |
| German Insurance Act (VAG) | German insurance supervision |

**Telecommunications:**

| Regulation | Coverage |
|------------|----------|
| ePrivacy Directive | Electronic communications privacy |
| PECR | Privacy and Electronic Communications Regulations |
| NIS2 Directive | Network and information systems security |

196 countries. 30+ controls. Every policy signed against the applicable regulatory framework for your jurisdiction and industry.

---

## Framework Support

| Framework | Status |
|-----------|--------|
| LangGraph | Supported |
| LangChain | Supported |
| CrewAI | Supported |
| OpenAI | Supported |
| Google ADK | Supported |
| Pydantic AI | Supported |
| LlamaIndex | Supported |
| AutoGen | Supported |
| Smolagents | Supported |
| Plain Python | Supported |

One SDK. One gateway. One audit chain. Any framework. Any cloud. Any agent.

---

## Try Before You Code

Visit [phronedge.com/playground](https://phronedge.com/playground) to see runtime governance in action. Pick an industry (insurance, healthcare, finance, technology). Paste your OpenAI or Gemini API key. Chat with a governed agent. Watch every checkpoint fire in real time. No signup required. 30 seconds.

---

## Get Started

```bash
pip install phronedge
```

```python
from phronedge import PhronEdge

pe = PhronEdge()

@pe.govern("my_tool")
def my_tool(param: str) -> str:
    return your_existing_function(param)
```

<div align="center">

Built for the EU AI Act era.

**[phronedge.com](https://phronedge.com)**

</div>
