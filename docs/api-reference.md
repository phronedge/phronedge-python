# API Reference

Base URL: `https://api.phronedge.com/api/v1`

All endpoints require the `X-PhronEdge-Key` header unless otherwise noted.

## Authentication

### GET /auth/credential

Fetch the signed credential for an agent.

**Headers:**
```
X-PhronEdge-Key: pe_live_your_key_here
```

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | str | No | Agent ID to fetch. Without this, returns the first available credential under your tenant |

**Request:**
```bash
curl -s "https://api.phronedge.com/api/v1/auth/credential?agent_id=fraud-analyst" \
  -H "X-PhronEdge-Key: pe_live_your_key_here"
```

**Response (200):**
```json
{
  "credential": {
    "credential_id": "cred-fraud-analyst-a1b2c3d4",
    "agent_id": "fraud-analyst",
    "tier": "T2",
    "jurisdiction": "DE",
    "permitted_tools": {
      "claim_lookup": {
        "permissions": ["read"],
        "jurisdictions": ["DE", "AT", "CH"],
        "data_classification": "PII"
      }
    },
    "permitted_models": ["gpt-4o"],
    "frameworks": ["GDPR", "EU AI Act", "ISO 42001"],
    "phronedge_signature": "3045...",
    "policy_hash": "a1b2c3..."
  },
  "agent_id": "fraud-analyst",
  "tenant_id": "tn_52447d402c904055",
  "environment": "live"
}
```

**Error responses:**

| Status | Reason |
|--------|--------|
| 401 | Missing or invalid API key |
| 404 | No credential found. Sign a policy first |

### POST /auth/keys/create

Create a new API key. Requires Firebase auth (Bearer token).

**Request:**
```json
{
  "agent_id": "",
  "label": "production"
}
```

**Response (200):**
```json
{
  "api_key": "pe_live_abc123...",
  "key_prefix": "pe_live_abc1...",
  "tenant_id": "tn_52447d402c904055",
  "label": "production",
  "message": "Store this key securely. It will not be shown again."
}
```

### GET /auth/keys

List API keys for your tenant. Returns prefixes only, never full keys.

### POST /auth/keys/revoke

Revoke an API key. Immediate. All requests using this key are rejected.

**Request:**
```json
{
  "key_prefix": "pe_live_abc1",
  "reason": "Compromised"
}
```

## Governance

### POST /governance/build

Sign a policy and register agents. Returns a signed artifact with ECDSA credential.

**Headers:**
```
X-PhronEdge-Key: pe_live_your_key_here
Content-Type: application/json
```

**Request body:**
```json
{
  "organization": {
    "name": "Your Company",
    "jurisdiction": "DE",
    "industry": "IN",
    "data_types": ["PUB", "PII"],
    "data_residency": ["DE"],
    "deployment_jurisdictions": ["DE", "AT", "CH"]
  },
  "agents": [{
    "id": "my-agent",
    "purpose": "Process insurance claims",
    "model": "gpt-4o",
    "tier": "T2",
    "role": "standalone",
    "data_classifications": ["PUB", "PII"],
    "tools": ["claim_lookup", "report_generate"],
    "host_jurisdiction": "DE",
    "serving_jurisdictions": ["DE", "AT", "CH"]
  }],
  "tools": [{
    "id": "claim_lookup",
    "description": "Search claims by ID",
    "type": "sdk",
    "data_classification": "PII",
    "permissions": ["read"],
    "jurisdictions": ["DE", "AT", "CH"],
    "deny_patterns": ["DROP", "DELETE", "TRUNCATE"]
  }]
}
```

**Response (200):**
```json
{
  "status": "compliant",
  "signed_artifact": {
    "policy_hash": "a1b2c3d4...",
    "frameworks": ["GDPR", "EU AI Act", "ISO 42001", "NIST AI RMF"],
    "controls_met": 30,
    "controls_required": 30,
    "agents": {
      "my-agent": {
        "permitted_tools": {
          "claim_lookup": {
            "permissions": ["read"],
            "jurisdictions": ["DE", "AT", "CH"],
            "deny_patterns": ["DROP", "DELETE", "TRUNCATE"]
          }
        }
      }
    }
  },
  "credentials_issued": [{
    "credential_id": "cred-my-agent-e5f6g7h8",
    "agent_id": "my-agent"
  }]
}
```

### Organization fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | str | Yes | Organization name |
| `jurisdiction` | str | Yes | Primary jurisdiction (ISO alpha-2) |
| `industry` | str | Yes | Industry code: `FI` (finance), `HC` (healthcare), `IN` (insurance), `TE` (technology), `GO` (government) |
| `data_types` | list | Yes | Data classifications: `PUB`, `INT`, `CONF`, `PII`, `PII_HEALTH`, `PII_FINANCIAL`, `RESTRICTED` |
| `data_residency` | list | Yes | Where data must reside (ISO alpha-2) |
| `deployment_jurisdictions` | list | Yes | Where agents will operate (ISO alpha-2) |

### Agent fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | str | Yes | Unique agent ID |
| `purpose` | str | Yes | What this agent does |
| `model` | str | Yes | LLM model name |
| `tier` | str | Yes | `T1` (sub-agent), `T2` (standalone), `T3` (orchestrator) |
| `role` | str | Yes | `standalone`, `sub_agent`, or `orchestrator` |
| `data_classifications` | list | Yes | Data levels this agent can access |
| `tools` | list | Yes | Tool IDs this agent can use |
| `host_jurisdiction` | str | Yes | Where this agent runs |
| `serving_jurisdictions` | list | Yes | Jurisdictions this agent serves |

### Tool fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | str | Yes | Unique tool ID. Must match `@pe.govern("id")` |
| `description` | str | Yes | What this tool does |
| `type` | str | Yes | `sdk`, `api`, or `mcp` |
| `data_classification` | str | Yes | Data level: `PUB`, `INT`, `PII`, etc. |
| `permissions` | list | Yes | Allowed actions: `read`, `write`, `delete`, `execute` |
| `jurisdictions` | list | Yes | Where this tool can be called from |
| `deny_patterns` | list | No | Input patterns to block: `DROP`, `DELETE`, `TRUNCATE`, etc. |
| `max_per_day` | int | No | Maximum calls per day |
| `requires_human_approval` | bool | No | Whether human approval is needed before execution |

## Gateway

### POST /gateway/proxy/{tool_name}

Route a governed tool call through the 7-checkpoint pipeline. Called by the SDK automatically.

**Headers:**
```
X-PhronEdge-Key: pe_live_your_key_here
X-Constitutional-Credential: {"credential_id": "...", ...}
Content-Type: application/json
```

**Request:**
```json
{
  "arguments": {"claim_id": "CLM-2026-001"},
  "action": "read",
  "jurisdiction": "DE"
}
```

**Response (200):** Tool call allowed. SDK executes the function.

**Response (403):** Tool call blocked.
```json
{
  "detail": {
    "reason": "Action 'delete' not permitted on tool 'claim_lookup'. Allowed: ['read']",
    "checkpoint": "judge",
    "error": "tool_blocked"
  }
}
```

### POST /gateway/scan

Pre-scan text for PII or prompt injection.

**Request:**
```json
{
  "text": "Customer SSN is 123-45-6789"
}
```

## Policy export

### GET /policy/export/{format}

Export the signed policy as OPA Rego, YAML, or JSON.

**Query parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | str | No | Agent ID to export |

**Formats:** `rego`, `yaml`, `json`

```bash
curl -s "https://api.phronedge.com/api/v1/policy/export/rego?agent_id=fraud-analyst" \
  -H "X-PhronEdge-Key: pe_live_your_key_here"
```

## Audit chain

### GET /tenant/chain

Fetch the audit event chain for your tenant.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Number of events to return |

**Response:**
```json
{
  "events": [
    {
      "event_type": "TOOL_CALL_ALLOWED",
      "agent_id": "fraud-analyst",
      "tool": "claim_lookup",
      "hash": "a7f3b2c9...",
      "prev_hash": "d1e4f5a6...",
      "timestamp": 1775980900
    }
  ],
  "chain_valid": true
}
```

## Agent lifecycle

### POST /agent/{agent_id}/quarantine

Quarantine an agent. All tool calls blocked immediately.

### POST /agent/{agent_id}/reinstate

Reinstate a quarantined agent. Tool calls resume.

## Rate limits

| Endpoint | Limit |
|----------|-------|
| GET /auth/credential | 30/minute |
| POST /auth/keys/create | 3/minute |
| POST /governance/build | 10/minute |
| POST /gateway/proxy/* | 600/minute |
| POST /gateway/scan | 60/minute |
