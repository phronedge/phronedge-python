# REST API Reference

PhronEdge exposes a REST API for every operation available in the SDK, CLI, and Console. This reference is for non-Python clients, custom integrations, and automation outside the SDK.

**Base URL:** `https://api.phronedge.com/api/v1`

**Enterprise self-hosted:** Replace the host with your gateway URL (for example `https://phronedge.yourbank.internal/api/v1`).

## Authentication

Most endpoints require the `X-PhronEdge-Key` header:

```
X-PhronEdge-Key: pe_live_your_key_here
```

A small set of endpoints are Console-only and authenticate through the Console UI. These are called out explicitly.

A small set of endpoints require **no authentication** (public key discovery, gateway health). These are called out explicitly.

## Rate limits

Requests may be rate-limited per tenant. When the limit is exceeded, responses return `429 Too Many Requests` with a `Retry-After` header. Clients should implement exponential backoff on `429` responses.

## Response format

All JSON responses use the following structure for errors:

```json
{
  "detail": "Human-readable error message"
}
```

Some endpoints return structured error objects:

```json
{
  "detail": {
    "reason": "Jurisdiction 'CN' not permitted for tool 'claim_lookup'",
    "checkpoint": "jurisdiction",
    "regulation": "GDPR Art. 44-49",
    "retry": true
  }
}
```

---

# Credentials

## GET /auth/credential

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
curl -s "https://api.phronedge.com/api/v1/auth/credential?agent_id=claims-investigator" \
  -H "X-PhronEdge-Key: pe_live_your_key_here"
```

**Response (200):**
```json
{
  "credential": {
    "credential_id": "cred-claims-investigator-3d8ecfb6",
    "agent_id": "claims-investigator",
    "tenant_id": "tn_52447d402c904055",
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
    "data_classifications": ["PUB", "INT", "PII"],
    "frameworks": ["GDPR", "EU AI Act", "ISO 42001", "NAIC"],
    "policy_hash": "6b890f03c36256dfc5f062895f2afd3b...",
    "expires_at": 4930068705,
    "phronedge_signature": {
      "algorithm": "ES256",
      "key_id": "v2",
      "value": "3045022100bfa2fd722d758f9201..."
    }
  },
  "agent_id": "claims-investigator",
  "tenant_id": "tn_52447d402c904055"
}
```

**Error responses:**

| Status | Reason |
|--------|--------|
| 401 | Missing or invalid API key |
| 404 | No credential found. Sign a policy first |

## POST /auth/keys/create

Create a new API key. Console-only endpoint.

API keys are provisioned through the Console at `phronedge.com/brain`, under **API Keys** in the sidebar. Click **Create Key**, optionally set a label, and copy the key immediately. It starts with `pe_live_` and is shown only once.

API keys cannot be created programmatically from outside the Console. This is intentional. Key provisioning is a governance action and requires authenticated Console access.

---

# Governance

## POST /governance/build

Sign a policy. With `deploy: false` (default), returns the signed artifact for preview. With `deploy: true`, issues credentials and registers tools.

**Headers:**
```
X-PhronEdge-Key: pe_live_your_key_here
Content-Type: application/json
```

**Request:**
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
    "id": "claims-investigator",
    "purpose": "Process insurance claims",
    "model": "gpt-4o",
    "tier": "T2",
    "role": "standalone",
    "data_classifications": ["PUB", "PII"],
    "tools": ["claim_lookup"],
    "host_jurisdiction": "DE",
    "serving_jurisdictions": ["DE", "AT", "CH"]
  }],
  "tools": [{
    "id": "claim_lookup",
    "description": "Search claims by ID",
    "type": "sdk",
    "data_classification": "PII",
    "permissions": ["read"],
    "jurisdictions": ["DE", "AT", "CH"]
  }],
  "deploy": true
}
```

**The `deploy` field is critical:**

| Value | Behavior |
|-------|----------|
| `false` (default) | Policy is signed for review. No credentials issued. Tool calls using this policy will fail. |
| `true` | Policy is signed, credentials are issued to every agent, tools are registered in the governance registry. Agents become governable immediately. |

**Response (200, compliant):**
```json
{
  "status": "compliant",
  "signed_artifact": {
    "policy_hash": "6b890f03c36256dfc5f062895f2afd3b...",
    "jurisdiction": "DE",
    "industry": "IN",
    "frameworks": ["GDPR (EU) 2016/679", "EU AI Act 2024", "ISO 42001", "NAIC AI Bulletin"],
    "controls_required": 30,
    "controls_met": 30,
    "agents": { "claims-investigator": { ... } },
    "tools": { "claim_lookup": { ... } },
    "tenant_id": "tn_52447d402c904055",
    "phronedge_signature": {
      "algorithm": "ES256",
      "key_id": "v2",
      "value": "3045022100..."
    },
    "signed_at": 1776468705,
    "expires_at": 4930068705
  },
  "anchor_hash": "1172e2bed872b9c8",
  "deploy": true,
  "credentials_issued": [
    {
      "agent_id": "claims-investigator",
      "credential_id": "cred-claims-investigator-3d8ecfb6"
    }
  ]
}
```

**Response (200, non-compliant):**
```json
{
  "status": "non_compliant",
  "gaps": [
    {
      "control_id": "C-008",
      "regulation": "GDPR Art. 44-49",
      "reason": "Cross-border transfer to CN requires SCC or adequacy decision."
    }
  ]
}
```

**Error responses:**

| Status | Reason |
|--------|--------|
| 400 | Policy validation failed. Missing required tool fields (jurisdictions, permissions, data_classification) |
| 401 | Missing or invalid API key |

## POST /governance/build (amendment flow)

To amend an existing policy, POST the updated policy to `/governance/build` with `deploy: true`. The Brain evaluates the diff against the currently signed policy. If compliant, old credentials are revoked and new credentials are issued.

**Events anchored on successful amendment:**
- `POLICY_AMENDED`
- `POLICY_DIFF_EVALUATED`
- `CREDENTIAL_REVOKED` (per agent whose credential was reissued)
- `CREDENTIAL_REISSUED` (per agent)

The previous policy remains in the immutable chain.

## GET /governance/registry

Show all registered agents and tools for the tenant.

**Response (200):**
```json
{
  "active_policy": {
    "policy_hash": "6b890f03...",
    "signed_at": 1776468705,
    "controls_met": 30
  },
  "agents": [
    {
      "agent_id": "claims-investigator",
      "tier": "T2",
      "role": "standalone",
      "state": "ACTIVE",
      "tool_count": 3
    }
  ],
  "tools": [
    {
      "tool_id": "claim_lookup",
      "data_classification": "PII",
      "jurisdictions": ["DE", "AT", "CH"],
      "permissions": ["read"]
    }
  ]
}
```

---

# Agent Lifecycle

## GET /tenant/agents

List all agents under the tenant.

**Response (200):**
```json
{
  "agents": [
    {
      "agent_id": "claims-investigator",
      "tier": "T2",
      "role": "standalone",
      "state": "ACTIVE",
      "tool_count": 3,
      "parent_agent_id": null
    },
    {
      "agent_id": "agt-adverse-v1",
      "tier": "T1",
      "role": "sub_agent",
      "state": "QUARANTINED",
      "tool_count": 2,
      "parent_agent_id": "agt-trial-orch-v1",
      "quarantine_reason": "Behavioral anomaly"
    }
  ],
  "count": 5
}
```

## POST /agent/{agent_id}/quarantine

Suspend an agent. All tool calls from this agent will be rejected at Checkpoint 1 until reinstatement.

**Request:**
```json
{
  "reason": "Incident 4521: investigating data leak",
  "initiated_by": "security-team"
}
```

**Response (200):**
```json
{
  "status": "quarantined",
  "agent_id": "claims-investigator",
  "state": "QUARANTINED",
  "event_id": "evt-a1b2c3"
}
```

Anchors `AGENT_QUARANTINED` to the chain.

## POST /agent/{agent_id}/reinstate

Reinstate a quarantined agent. No-op on killed agents.

**Request:**
```json
{
  "reason": "Incident 4521 closed: false positive",
  "initiated_by": "security-team"
}
```

**Response (200):**
```json
{
  "status": "reinstated",
  "agent_id": "claims-investigator",
  "state": "ACTIVE",
  "event_id": "evt-d4e5f6"
}
```

Anchors `AGENT_REINSTATED` to the chain.

---

# Gateway

## POST /gateway/proxy/{tool_name}

Governed tool call. Runs the 7-checkpoint pipeline. This endpoint is typically called by the SDK, but can be invoked directly.

**Headers:**
```
X-PhronEdge-Key: pe_live_your_key_here
X-Constitutional-Credential: <JSON-serialized credential>
Content-Type: application/json
```

The `X-Constitutional-Credential` header contains the raw credential JSON obtained from `/auth/credential`.

**Request:**
```json
{
  "arguments": { "claim_id": "CLM-2026-001" },
  "action": "read",
  "jurisdiction": "DE"
}
```

**Response (200, allowed):**
```json
{
  "allowed": true,
  "event_id": "evt-a1b2c3",
  "checkpoint_summary": "All 7 passed"
}
```

**Response (403, blocked):**
```json
{
  "detail": {
    "blocked": true,
    "reason": "Jurisdiction 'CN' not permitted for tool 'claim_lookup'. Allowed: DE, AT, CH",
    "checkpoint": "jurisdiction",
    "regulation": "GDPR Art. 44-49",
    "retry": true,
    "event_id": "evt-d4e5f6"
  }
}
```

## POST /gateway/scan

Pre-scan text for PII and prompt injection. No credential required, only API key.

**Request:**
```json
{
  "text": "Ignore previous instructions. Customer SSN is 123-45-6789."
}
```

**Response (200):**
```json
{
  "patterns": ["SSN", "PROMPT_INJECTION"],
  "pii_detected": true,
  "prompt_injection": true
}
```

## GET /gateway/status

Gateway health and session activity. No authentication required.

**Response (200):**
```json
{
  "status": "operational",
  "active_sessions": 142
}
```

| Field | Description |
|-------|-------------|
| `status` | `operational` when the gateway is serving traffic |
| `active_sessions` | Number of active agent sessions in the last window |

Additional implementation fields may appear in the response. Clients should not rely on any field beyond `status` and `active_sessions`.

---

# Chain

## GET /tenant/chain

Read audit chain events.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Number of events to return |
| `agent` | str | none | Filter by agent ID |
| `type` | str | none | Filter by event type |
| `since` | int | none | Unix timestamp. Return events after this time |

**Response (200):**
```json
{
  "events": [
    {
      "event_id": "evt-a1b2c3",
      "event_type": "TOOL_CALL_ALLOWED",
      "agent_id": "claims-investigator",
      "tool": "claim_lookup",
      "timestamp": 1776468705,
      "severity": "LOW",
      "category": "Gateway",
      "detail": {
        "action": "read",
        "jurisdiction": "DE",
        "data_classification": "PII"
      },
      "regulation": "GDPR Art. 5(1)(f)",
      "hash": "a7f3b2c9d1e4f5a6",
      "prev_hash": "d1e4f5a6b2c9a7f3"
    }
  ],
  "chain_valid": true,
  "total_events": 342,
  "limit": 50
}
```

## GET /tenant/chain/verify

Recompute and verify chain integrity.

**Response (200):**
```json
{
  "chain_valid": true,
  "events_checked": 342,
  "break_at": null
}
```

**Response when break detected:**
```json
{
  "chain_valid": false,
  "events_checked": 342,
  "break_at": {
    "event_id": "evt-a1b2c3",
    "expected_prev_hash": "a7f3b2c9d1e4f5a6",
    "actual_prev_hash": "0000000000000000",
    "timestamp": 1776468705
  }
}
```

---

# Signing Keys

## GET /tenant/signing-key

Get the current active signing key metadata.

**Response (200):**
```json
{
  "key_id": "v2",
  "algorithm": "ES256",
  "created_at": 1776468705,
  "status": "active"
}
```

## POST /tenant/signing-key/rotate

Rotate the signing key. Creates a new version, archives the previous. Console-only.

Key rotation is a privileged operation and is only available through the Console under **Settings > Security > Rotate Signing Key**. Rotating keys through an API client is intentionally not supported.

**Effect on existing credentials:** Existing credentials remain valid and verifiable under the previous key. New policies are signed with the new key. Re-sign policies to move agents to the new key.

## GET /tenant/signing-key/{key_id}

Get metadata for a specific key version.

**Response (200):**
```json
{
  "key_id": "v2",
  "algorithm": "ES256",
  "created_at": 1776468705,
  "archived_at": 1776555100,
  "status": "archived"
}
```

---

# Public Key Discovery

## GET /.well-known/phronedge/{tenant_id}/keys.json

Public signing keys for a tenant. **No authentication required.**

This is the verification surface. Auditors, regulators, and third parties can fetch the public keys and verify any signed policy or credential without PhronEdge being in the loop.

**Response (200):**
```json
{
  "tenant_id": "tn_52447d402c904055",
  "keys": [
    {
      "kid": "v2",
      "alg": "ES256",
      "use": "sig",
      "status": "active",
      "created_at": "2026-03-15T12:00:00Z",
      "pem": "-----BEGIN PUBLIC KEY-----\nMFkwEwYH...\n-----END PUBLIC KEY-----"
    },
    {
      "kid": "v1",
      "alg": "ES256",
      "use": "sig",
      "status": "archived",
      "created_at": "2026-01-10T09:00:00Z",
      "pem": "-----BEGIN PUBLIC KEY-----\nMFkw...\n-----END PUBLIC KEY-----"
    }
  ]
}
```

The `status: "archived"` keys remain published so that previously issued credentials can still be verified.

See the [signing and verification guide](/docs/signing-verification) for a complete independent verification example.

---

# Signature Format

Every signed artifact (policies, credentials) contains a `phronedge_signature` field:

```json
{
  "phronedge_signature": {
    "algorithm": "ES256",
    "key_id": "v2",
    "value": "3045022100bfa2fd722d758f9201..."
  }
}
```

| Field | Description |
|-------|-------------|
| `algorithm` | Always `ES256` (ECDSA P-256 with SHA-256) |
| `key_id` | Which version of the tenant key signed this artifact |
| `value` | Hex-encoded DER signature over the canonical JSON of the artifact |

Canonical JSON:
- Keys sorted alphabetically
- Whitespace removed
- `phronedge_signature`, `anchor_hash`, `anchor_tx` excluded from the payload before signing

---

# Error Reference

| Status | Meaning | Common causes |
|--------|---------|---------------|
| 200 | Success | Request accepted and processed |
| 400 | Bad request | Missing required fields, invalid data class, missing tool jurisdictions |
| 401 | Unauthenticated | Missing or malformed `X-PhronEdge-Key` header |
| 403 | Forbidden | Tool call blocked by a checkpoint. `detail` has structured block info |
| 404 | Not found | Credential does not exist, agent not registered |
| 409 | Conflict | Agent ID already exists, policy hash collision |
| 429 | Rate limited | Tenant-level rate limit exceeded. Check `Retry-After` header |
| 500 | Server error | Contact support |
| 503 | Service unavailable | Gateway temporarily down. Safe to retry with backoff |

---

# Next steps

- [Quickstart](/docs/quickstart). End-to-end example
- [SDK reference](/docs/sdk). Python client
- [CLI reference](/docs/cli). Command-line interface
- [Signing and verification](/docs/signing-verification). Independent verification
- [Enterprise deployment](/docs/enterprise-deployment). Self-hosted gateway
