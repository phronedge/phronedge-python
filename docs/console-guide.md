# Console Guide

The PhronEdge Console at [phronedge.com/brain](https://phronedge.com/brain) is where CISOs, compliance officers, and platform engineers manage AI governance. Developers run the CLI and SDK. The Console is the governance surface.

This guide describes the Console's structure, the primary workflows, and which surface (SDK, CLI, or Console) is appropriate for each operation.

## The Console at a glance

The Console has five primary views plus a Settings panel.

| View | Audience | Purpose |
|------|----------|---------|
| Policy Builder | Platform team, CISO | Define and sign governance policies |
| Architecture | Architecture review, CISO | Visualize the signed governance structure |
| Observer | CISO, SOC team | Real-time monitoring, agent lifecycle |
| Audit Log | Compliance, auditors | Searchable event history with regulatory citations |
| API Keys | Platform team | Provision SDK credentials |

## Policy Builder

A step-by-step form that produces a signed constitutional policy. No code required.

The Builder walks through three logical steps:

**Organization.** Your regulatory context. HQ jurisdiction, industry, data types handled, data residency, deployment jurisdictions. These inputs drive the Brain's framework resolution.

**Agents and Tools.** Every AI agent you deploy, its tier, its data clearance, its tool access, its behavioral baseline, its token budget. Every tool, its data classification, minimum tier, allowed jurisdictions, and permissions.

**Organization Policy.** Tenant-wide ceiling. Allowed models, global deny patterns, auto-quarantine triggers, escalation rules, threat detection settings.

Click **Sign and Deploy**. The Brain evaluates against applicable regulatory frameworks. Compliant policies are signed, credentials are issued, events are anchored. Policies with gaps return a remediation report.

The Builder has two action modes: **Build** (signs for review, no credentials issued) and **Sign and Deploy** (issues credentials). Build is for pre-approval review. Sign and Deploy is the production commitment.

## Architecture View

Renders the signed policy as an interactive governance graph. Organization at top. Agents below. Orchestrators above their sub-agents with parent-child edges. Tools below the agents that use them.

Click any node to see its full configuration.

Every signed policy is viewable as:

- **JSON** - Machine-readable artifact
- **YAML** - Human-readable for version control
- **OPA Rego** - Complete policy bundle with denial reasons and regulation citations

Export artifacts directly to your version control, object storage, or custom webhook from the Export action.

## Observer

Real-time governance monitoring. The operational surface for your SOC team.

**Top metrics:** Requests allowed, requests blocked, PII detections, injection attempts, tamper events, lifecycle events. Updated live.

**Events chart:** Time-series of allowed vs blocked activity.

**Agent fleet:** Every agent as a card showing state (Active, Quarantined, Killed), tool count, recent activity, and action buttons. Sub-agents nest inside their orchestrator's card.

**Activity feed:** Real-time scrolling event list with regulation citations. Click for full event details including SHA-256 hash and chain linkage.

**System status:** Live status of each of the five powers (Observer, Judge, Enforcer, Brain, Anchor).

**Constitutional Laws panel:** The four principles that govern PhronEdge's enforcement decisions.

## Audit Log

Searchable, filterable history of every governance event. Separate from the live feed.

Filter by agent, event type, severity, category, or date range. Export the filtered view as a signed audit pack.

Every event shows its regulation citation, the checkpoint that triggered it, and its place in the cryptographic chain.

## Settings

Tenant administration. Profile, team and permissions, security, integration, and the Danger Zone.

**Team and Permissions** supports role-based access with separation between policy signing, agent lifecycle, audit review, and tenant administration.

**Security** shows the active signing key and provides key rotation. Key rotation is Console-only.

**Danger Zone** handles tenant deletion with multi-step confirmation.

## Which surface for which operation

The product has three surfaces: SDK (runtime), CLI (developer and CI/CD), Console (governance). Each is designed for a specific audience and a specific set of operations.

| Operation | Surface | Why |
|-----------|---------|-----|
| Runtime tool governance | SDK | Enforcement happens at every call |
| Policy build in CI | CLI | Scriptable, version-controllable |
| Policy signing and deployment | CLI or Console | Either is authoritative |
| Policy review and visualization | Console | Visual architecture graph |
| Real-time monitoring | Console | Live telemetry, agent cards |
| Agent quarantine | CLI, SDK, Console | Reversible, multiple paths |
| Kill switch | Console only | Permanent, requires authenticated session |
| Signing key rotation | Console only | Privileged, multi-step confirmation |
| Team management | Console only | Tenant administration |
| Chain verification | CLI or Console | Same cryptographic check |
| Audit export | CLI or Console | Signed artifacts, same format |

**Pattern:** Reversible operations are available in all three surfaces. Privileged or irreversible operations are Console-only to enforce authenticated session context.

## Dual-track workflows

Common operations have both a developer path and a CISO path.

**Signing a policy.** Developer runs `phronedge policy deploy policy.yaml` in CI. CISO walks through the Policy Builder and clicks Sign and Deploy. Both produce the same signed artifact and the same `POLICY_SIGNED` event.

**Verifying the chain.** Developer runs `phronedge chain verify`. CISO clicks the Verify hash chain button in the Observer. Same cryptographic check. Same result.

**Quarantining an agent.** Developer calls `pe.quarantine()` or runs `phronedge agent quarantine`. CISO clicks the Quarantine button on the agent card. Same effect.

**Exporting for audit.** Developer runs `phronedge export rego`. CISO opens the Architecture view and copies the OPA tab. Same Rego bundle with the same regulatory citations.

This dual-track design is deliberate. It ensures that every operation with enterprise significance is accessible to the person responsible for the decision, whether that person works in code or through a browser.

## Observer and human oversight

Regulated AI deployments require demonstrable human oversight. The Observer is the oversight surface.

The Observer provides what regulators expect to see:

- Real-time visibility into agent behavior
- Immediate intervention controls (quarantine, reinstate, kill)
- Cryptographic proof that past events have not been modified
- Regulatory citation on every blocked event

Your regulator asking "how does a human intervene" points to the Observer and its agent lifecycle controls. Your compliance team's evidence of effective oversight is the chain of authenticated Console actions, all signed and anchored.

## Getting full detail

The Policy Builder field reference, the Settings admin guide, the complete operator playbook for each Console action, and the full SDK-CLI-Console capability matrix are available to registered customers.

## Next steps

- [Quickstart](/docs/quickstart). Two-minute end-to-end
- [Compliance matrix](/docs/compliance-matrix). Which regulation each Console feature satisfies
- [Signing and verification](/docs/signing-verification). What the Console is signing on your behalf
- [Threat model](/docs/threat-model). The trust model behind the Console
- [CLI reference](/docs/cli). Developer-side equivalents
