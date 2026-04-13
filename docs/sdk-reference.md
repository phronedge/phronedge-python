# SDK Reference

Complete reference for the PhronEdge Python SDK.

## Installation

```bash
pip install phronedge
```

## PhronEdge class

```python
from phronedge import PhronEdge

pe = PhronEdge(
    api_key=None,         # reads PHRONEDGE_API_KEY env var if not set
    gateway_url=None,     # reads PHRONEDGE_GATEWAY_URL or defaults to https://api.phronedge.com/api/v1
    timeout=30,           # request timeout in seconds
    raise_on_block=False, # if True, blocked calls raise GovernanceError instead of returning JSON
    agent_id=None,        # agent ID to fetch credential for (one key, many agents)
)
```

### Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | str | None | API key starting with `pe_live_`. If not set, reads from `PHRONEDGE_API_KEY` environment variable |
| `gateway_url` | str | None | Gateway URL. If not set, reads from `PHRONEDGE_GATEWAY_URL` or defaults to `https://api.phronedge.com/api/v1` |
| `timeout` | int | 30 | Request timeout in seconds for all gateway calls |
| `raise_on_block` | bool | False | When True, blocked tool calls raise `GovernanceError`. When False, they return a JSON dict with block details |
| `agent_id` | str | None | Agent ID to fetch credential for. Allows one API key to govern multiple agents under the same tenant |

### Environment variables

| Variable | Description |
|----------|-------------|
| `PHRONEDGE_API_KEY` | Your API key. Required unless passed to constructor |
| `PHRONEDGE_GATEWAY_URL` | Gateway URL override. Useful for local development |

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

The function does not execute. A JSON dict is returned:

```python
{
    "blocked": True,
    "reason": "Action 'delete' not permitted on tool 'claim_lookup'. Allowed: ['read']",
    "checkpoint": "judge",
    "retry": True,
    "message": "Tool call blocked by PhronEdge governance."
}
```

This is recommended for agentic frameworks where the LLM needs to see the block reason and adapt.

### raise_on_block=True

The function does not execute. A `GovernanceError` (or subclass) is raised:

```python
from phronedge import PhronEdge, GovernanceError, ToolBlocked, AgentTerminated

pe = PhronEdge(raise_on_block=True)

try:
    result = my_tool("arg")
except ToolBlocked as e:
    print(e.checkpoint)   # which checkpoint blocked it
    print(e.regulation)   # which regulation triggered it
    print(e.retry)        # True if retryable
except AgentTerminated as e:
    print("Agent has been permanently killed")
except GovernanceError as e:
    print("General governance error")
```

## Exception classes

| Class | Parent | Description |
|-------|--------|-------------|
| `GovernanceError` | `Exception` | Base class for all governance errors |
| `ToolBlocked` | `GovernanceError` | Tool call blocked. May be retried |
| `AgentTerminated` | `GovernanceError` | Agent permanently killed. Not retryable |

### GovernanceError attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `message` | str | Human-readable reason |
| `checkpoint` | str | Which checkpoint blocked: `credential_validator`, `judge`, `jurisdiction`, `behavioral`, `pii_scanner`, `output_filter` |
| `regulation` | str | Regulation that triggered the block: `GDPR Art. 44-49`, `EU AI Act Art. 14`, etc. |

### ToolBlocked attributes

All `GovernanceError` attributes plus:

| Attribute | Type | Description |
|-----------|------|-------------|
| `retry` | bool | Whether the call can be retried. False if agent is quarantined |

## Utility methods

### pe.scan(text)

Pre-scan text for PII or prompt injection before sending to an LLM.

```python
result = pe.scan("Customer SSN is 123-45-6789")
# {"pii_detected": True, "patterns": ["SSN"], "risk": "high"}
```

### pe.status()

Check gateway status.

```python
result = pe.status()
# {"status": "ok", "version": "2.5", "uptime": 86400}
```

### pe.quarantine(reason)

Quarantine the agent. All tool calls blocked immediately. No restart needed.

```python
pe.quarantine(reason="Anomalous behavior detected")
```

### pe.reinstate(reason)

Reinstate a quarantined agent. Tool calls resume immediately.

```python
pe.reinstate(reason="Investigation complete, behavior normal")
```

### pe.kill()

Kill switch is only available through the PhronEdge console at phronedge.com/brain. The SDK raises `GovernanceError` if called.

## Credential caching

The SDK caches the credential for 5 minutes after fetching from the gateway. This means the first call in a session makes one HTTP request to `/auth/credential`, and subsequent calls reuse the cached credential until it expires.

To force a fresh credential fetch:

```python
pe._credential = None
pe._credential_ts = 0
```
