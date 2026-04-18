# SDK Reference

Complete reference for the PhronEdge Python SDK.

Current version: `2.4.6`

## Installation

```bash
pip install phronedge
```

Requires Python 3.9 or higher. Works with any framework. No additional dependencies.

## PhronEdge class

```python
from phronedge import PhronEdge

pe = PhronEdge(
    api_key=None,         # reads PHRONEDGE_API_KEY env var if not set
    gateway_url=None,     # reads PHRONEDGE_GATEWAY_URL or defaults to https://api.phronedge.com/api/v1
    timeout=30,           # request timeout in seconds
    raise_on_block=False, # if True, blocked calls raise ToolBlocked instead of returning a dict
    agent_id=None,        # agent ID to fetch credential for (one key, many agents)
)
```

### Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | str | None | API key starting with `pe_live_`. If not set, reads from `PHRONEDGE_API_KEY` environment variable |
| `gateway_url` | str | None | Gateway URL. If not set, reads from `PHRONEDGE_GATEWAY_URL` or defaults to `https://api.phronedge.com/api/v1` |
| `timeout` | int | 30 | Request timeout in seconds for all gateway calls |
| `raise_on_block` | bool | False | When True, blocked tool calls raise `ToolBlocked`. When False, they return a dict with block details |
| `agent_id` | str | None | Agent ID to fetch credential for. Allows one API key to govern multiple agents under the same tenant |

### Environment variables

| Variable | Description |
|----------|-------------|
| `PHRONEDGE_API_KEY` | Your API key. Required unless passed to constructor |
| `PHRONEDGE_GATEWAY_URL` | Gateway URL override. Useful for enterprise self-hosted and local development |
| `PHRONEDGE_AGENT_ID` | Default agent ID. Can be overridden by the constructor parameter |

### Multi-agent tenants

When one API key owns multiple agents, pass `agent_id` explicitly so the SDK fetches the right credential:

```python
pe_fraud = PhronEdge(agent_id="fraud-analyst")
pe_kyc   = PhronEdge(agent_id="kyc-verifier")
```

Without `agent_id`, the SDK fetches the first available credential. This is fine for single-agent tenants but unreliable with multiple agents.

## govern() decorator

```python
@pe.govern(tool_name, action="execute", jurisdiction=None, mcp=None, delegates=None)
def my_tool(arg1, arg2):
    ...
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tool_name` | str | required | Must match a tool ID in your signed policy |
| `action` | str | `"execute"` | Permission level: `read`, `write`, `delete`, or `execute` |
| `jurisdiction` | str | None | ISO alpha-2 country code. Gateway checks against the tool's allowed jurisdiction list |
| `mcp` | str | None | MCP server URL for tool discovery |
| `delegates` | list | None | Agent IDs this call can delegate to |

### Decorator order

When combining with framework decorators, PhronEdge must be the inner decorator:

```python
# LangGraph / LangChain
@tool
@pe.govern("my_tool", action="read")
def my_tool(): ...

# CrewAI
@tool("my_tool")
@pe.govern("my_tool", action="read")
def my_tool(): ...

# OpenAI Agents
@function_tool
@pe.govern("my_tool", action="read")
def my_tool(): ...

# LlamaIndex (no framework decorator needed)
@pe.govern("my_tool", action="read")
def my_tool(): ...

# Google ADK (no framework decorator needed)
@pe.govern("my_tool", action="read")
def my_tool(): ...
```

## Behavior on block

### raise_on_block=False (default)

The function body does not execute. A dict is returned:

```python
{
    "blocked": True,
    "reason": "Action 'delete' not permitted on tool 'claim_lookup'. Allowed: read, execute",
    "checkpoint": "judge",
    "regulation": "EU AI Act Art. 14",
    "retry": True,
    "message": "Tool call blocked by PhronEdge governance."
}
```

This is recommended for agentic frameworks where the LLM needs to see the block reason and adapt its next action.

### raise_on_block=True

The function body does not execute. A `ToolBlocked` (or `AgentTerminated`) exception is raised:

```python
from phronedge import PhronEdge, GovernanceError, ToolBlocked, AgentTerminated

pe = PhronEdge(raise_on_block=True)

try:
    result = my_tool("arg")
except AgentTerminated as e:
    # Agent has been permanently killed. Not retryable.
    log_kill_event(e)
except ToolBlocked as e:
    print(e.reason)       # "Action 'delete' not permitted..."
    print(e.checkpoint)   # "judge"
    print(e.regulation)   # "EU AI Act Art. 14"
    print(e.retry)        # True
    print(e.blocked)      # True
except GovernanceError as e:
    # Base class. Catch infrastructure failures (gateway unreachable, invalid key).
    handle_infra_error(e)
```

Order `except` clauses from most specific to most general. `AgentTerminated` before `ToolBlocked` before `GovernanceError`.

## Exception classes

| Class | Parent | When raised |
|-------|--------|-------------|
| `GovernanceError` | `Exception` | Base class. Infrastructure errors (gateway unreachable, invalid API key, 5xx). |
| `ToolBlocked` | `GovernanceError` | Tool call blocked by a checkpoint. May be retried. |
| `AgentTerminated` | `GovernanceError` | Agent has been permanently killed. Not retryable. |

### Common attributes

All three exception classes expose the same attribute set for consistent error handling:

| Attribute | Type | Description |
|-----------|------|-------------|
| `reason` | str | Human-readable reason for the block |
| `checkpoint` | str | Which checkpoint blocked: `credential_validator`, `jurisdiction`, `judge`, `tool_permission`, `pii_scanner`, `behavioral`, `output_filter` |
| `regulation` | str | Regulation that triggered the block (e.g. `GDPR Art. 44-49`, `EU AI Act Art. 14`) |
| `retry` | bool | Whether the call can be retried. False when the agent is quarantined or killed |
| `blocked` | bool | True when the tool was blocked by governance. False for pure infrastructure errors |

All attributes are populated. Accessing any attribute on any exception will not raise `AttributeError`.

## Utility methods

### pe.scan(text)

Pre-scan text for PII or prompt injection before sending to an LLM. Useful for catching risky input before it hits a tool.

```python
result = pe.scan("Customer SSN is 123-45-6789")
# {
#   "patterns": ["SSN"],
#   "pii_detected": True,
#   "prompt_injection": False
# }
```

Returns an empty dict if the gateway is unreachable. Never raises.

### pe.status()

Check gateway status and session activity.

```python
result = pe.status()
# {
#   "status": "operational",
#   "active_sessions": 2
# }
```

| Field | Description |
|-------|-------------|
| `status` | `operational` when the gateway is serving traffic |
| `active_sessions` | Active agent sessions in the last window |

Additional implementation fields may appear. Only `status` and `active_sessions` are guaranteed.

Returns an `{"error": ...}` dict on failure. Never raises.

## Agent lifecycle methods

The SDK can suspend and reinstate its own agent. This is useful for self-quarantine when the application detects anomalous behavior.

### pe.quarantine(reason)

Suspend all tool access for the agent. All subsequent calls are blocked at the gateway. Reversible with `pe.reinstate()`.

```python
pe.quarantine(reason="Anomalous behavior detected: 30 calls in 10 seconds")
```

Anchors `AGENT_QUARANTINED` event to the audit chain. Takes effect within one second.

### pe.reinstate(reason)

Restore tool access for a quarantined agent. Has no effect on a killed agent.

```python
pe.reinstate(reason="Investigation complete. Behavior normalized.")
```

Anchors `AGENT_REINSTATED` event to the audit chain.

### pe.kill()

The kill switch is not available through the SDK. Kill is permanent and irreversible, so it is restricted to the Console. Calling `pe.kill()` raises `GovernanceError` with a message directing you to the Console at `phronedge.com/brain`.

## The 7 checkpoints

Every governed tool call passes through 7 checkpoints in the gateway. The function body does not execute until all 7 pass.

| # | Checkpoint | Common block reasons |
|---|------------|---------------------|
| 1 | Credential Validator | Expired credential, invalid signature, revoked credential |
| 2 | PII Detector | Personal data in input triggers session elevation or block |
| 3 | Jurisdiction Router | Call jurisdiction not in tool's allowed list |
| 4 | Behavioral Baseline | Call rate exceeds spike multiplier on baseline |
| 5 | Judge | Tool not in permitted_tools, action not in permissions, tier insufficient |
| 6 | Data Classifier | Response data class exceeds agent clearance |
| 7 | Output Constraint | Output redaction rule triggered |

The checkpoint that blocked the call is available as `e.checkpoint` on the exception (or `result["checkpoint"]` in soft-block mode).

## Credential caching

The SDK caches the credential for 5 minutes after the first fetch. This means the first call in a session makes one HTTP request to `/auth/credential`, and subsequent calls reuse the cached credential until it expires.

To force a fresh credential fetch:

```python
pe._credential = None
pe._credential_ts = 0
```

This is rarely needed. The credential auto-refreshes. Use this only when you know the credential has changed out-of-band (for example, immediately after a policy amendment from a different session).

## Thread safety

One `PhronEdge` instance is safe to share across threads. The underlying `requests.Session` is thread-safe for read operations, and the credential cache is single-writer.

For async frameworks, the SDK uses synchronous HTTP calls via `requests`. For high-throughput async workloads, run the decorated function in a thread pool:

```python
import asyncio
result = await asyncio.to_thread(my_governed_tool, "arg")
```

## Versioning

| Version | Notes |
|---------|-------|
| 2.4.6 | Current stable. Full exception attribute set (`reason`, `blocked`, `retry`, `regulation`, `checkpoint`). Soft-block returns dict, not JSON string. |
| 2.4.x | Enterprise signer and vault backends. Per-tenant key rotation. |
| 2.3.x | Initial multi-agent support. |

Upgrade:

```bash
pip install --upgrade phronedge
```

## Next steps

- [Quickstart](/docs/quickstart). 2-minute end-to-end
- [CLI reference](/docs/cli). All 14 commands
- [REST API reference](/docs/api). For non-Python clients
- [Framework guides](/docs/frameworks). LangGraph, CrewAI, Google ADK, OpenAI Agents, LlamaIndex
- [Multi-agent governance](/docs/multi-agent). Orchestrators, sub-agents, delegation
- [Signing and verification](/docs/signing-verification). ECDSA signatures, independent verification
