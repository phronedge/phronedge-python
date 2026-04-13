# Console Guide

The PhronEdge console at [phronedge.com/brain](https://phronedge.com/brain) is where you sign policies, monitor agents, export credentials, and manage your tenant.

## Policy Builder

The Policy Builder is where you define your organization, agents, and tools.

### Starting a policy

1. Go to [phronedge.com/brain](https://phronedge.com/brain) and sign in
2. Click **Build Policy** or select a template
3. Fill in your organization details

### Templates

The Policy Builder includes pre-built templates for common industries:

- **Financial Services** (KYC, AML, fraud detection)
- **Healthcare** (claims processing, patient data)
- **Insurance** (claims investigation, risk assessment)
- **Technology** (data processing, API governance)

Each template pre-fills the organization settings, suggested agents, and tools with appropriate data classifications and jurisdictions.

### Defining agents

For each agent, specify:

- **Agent ID**: Unique identifier like `fraud-analyst` or `agt-kyc-v1`
- **Purpose**: What this agent does
- **Model**: LLM model it uses
- **Tier**: T1 (sub-agent), T2 (standalone), or T3 (orchestrator)
- **Data classifications**: What data levels it can access
- **Tools**: Which tools it can use
- **Jurisdictions**: Where it operates

### Defining tools

For each tool, specify:

- **Tool ID**: Must match the `@pe.govern("tool_id")` in your code
- **Description**: What this tool does
- **Permissions**: `read`, `write`, `delete`, `execute`
- **Jurisdictions**: Where this tool can be called from
- **Data classification**: Data level of this tool's output
- **Deny patterns**: Input patterns to block (SQL injection, etc.)
- **Rate limit**: Maximum calls per day

### Signing

Click **Build and Deploy** to sign the policy. The gateway:

1. Maps your organization to 199 jurisdictions
2. Identifies applicable regulatory frameworks
3. Evaluates 30 controls against your configuration
4. Signs the credential with ECDSA P-256
5. Anchors the policy hash to the audit chain
6. Issues credentials for each agent

After signing, you auto-navigate to the Architecture view.

## Architecture view

The Architecture view shows your signed policy in three formats:

### JSON tab

The raw signed credential as JSON. Includes the ECDSA signature, policy hash, permitted tools, frameworks, and all governance constraints.

### YAML tab

The same credential as YAML. Useful for configuration management and GitOps workflows.

### OPA tab

A complete OPA Rego policy bundle generated from your signed credential. Includes:

- Default deny rule
- Agent authorization
- Tool permissions with per-tool jurisdiction enforcement
- Model allowlist
- Data classification checks
- PII detection patterns
- Jurisdiction validation with cross-border transfer rules
- Behavioral baseline limits
- Delegation rules
- Output constraints
- Denial reason mapping
- Policy metadata with regulatory citations

Copy this file and drop it into any OPA runtime:

```bash
cp phronedge_policy.rego /path/to/opa/policies/
opa run --server --bundle /path/to/opa/policies/
```

### DAG graph

A visual directed acyclic graph showing your agents, tools, and delegation relationships.

## Observer

The Observer is the real-time audit trail for your tenant. Every tool call, whether allowed or blocked, appears here.

### Event types

| Event | Description |
|-------|-------------|
| `TOOL_CALL_ALLOWED` | Tool call passed all 7 checkpoints |
| `TOOL_CALL_BLOCKED` | Tool call blocked at a checkpoint |
| `PII_INPUT_DETECTED` | PII found in tool input |
| `PII_OUTPUT_DETECTED` | PII found in tool output |
| `POLICY_SIGNED` | New policy signed |
| `CREDENTIAL_ISSUED` | New credential issued |
| `AGENT_QUARANTINED` | Agent quarantined |
| `AGENT_REINSTATED` | Agent reinstated |
| `AGENT_KILLED` | Agent permanently terminated |
| `BEHAVIORAL_ANOMALY` | Tool call rate exceeded baseline |
| `VAULT_TAMPER_DETECTED` | Credential tampering detected |
| `VAULT_CREDENTIAL_RESTORED` | Credential restored after tamper |
| `DELEGATION_BLOCKED` | Unauthorized delegation attempt |

### Event details

Each event shows:

- **Agent ID**: Which agent made the call
- **Tool**: Which tool was called
- **Action**: What action was attempted
- **Checkpoint**: Which checkpoint allowed or blocked
- **Regulation**: Which regulation applies
- **Hash**: SHA-256 hash of this event
- **Previous hash**: Hash of the previous event (chain integrity)
- **Timestamp**: When the event occurred

### Chain integrity

Every event is SHA-256 hashed and chained to the previous event. If any event is tampered with, the chain breaks and `VAULT_TAMPER_DETECTED` is logged. The Observer shows chain integrity status.

## API Keys

Manage your tenant API keys:

- **Create Key**: Generate a new key. The full key is shown once
- **List Keys**: See all keys with prefixes, labels, and usage counts
- **Revoke Key**: Immediately revoke a key. All requests using it are rejected
- **Delete Key**: Permanently remove a key from the system

Keys are tenant-wide. One key works for all agents under your tenant.

## Agent lifecycle

### Quarantine

Quarantine an agent from the console. All tool calls from that agent are immediately blocked. No code change or restart needed.

### Reinstate

Reinstate a quarantined agent. Tool calls resume immediately.

### Kill

Permanently terminate an agent. This is irreversible. The agent credential is revoked and cannot be restored.

## Danger Zone

Account management:

- **Export data**: Download all your tenant data (GDPR Art. 20)
- **Close account**: Delete your account and all associated data (GDPR Art. 17). Requires typed confirmation. 30-day grace period before permanent deletion
- **Cancel closure**: Cancel a pending account closure during the grace period
