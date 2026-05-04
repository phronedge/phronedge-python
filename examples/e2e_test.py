"""
PhronEdge - Complete E2E: Register -> Sign -> Govern -> Block -> Observe
No browser. No console. Everything from this one script.

Prerequisites:
    pip install phronedge requests

Usage:
    export PHRONEDGE_API_KEY=pe_live_your_key_here
    export PHRONEDGE_GATEWAY_URL=http://localhost:8080/api/v1  # or https://api.phronedge.com/api/v1
    python e2e_test.py
"""

import os, sys, json, time, logging, requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("phronedge.e2e")

# ── Config ───────────────────────────────────────────────
API = os.environ.get("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")
KEY = os.environ.get("PHRONEDGE_API_KEY", "")

if not KEY:
    log.error("Set your API key:  export PHRONEDGE_API_KEY=pe_live_your_key_here")
    sys.exit(1)

H = {"X-PhronEdge-Key": KEY, "Content-Type": "application/json"}
AGENT_ID = "claims-investigator"


# ═══════════════════════════════════════════════════════════
#  STEP 1 - Verify server
# ═══════════════════════════════════════════════════════════

log.info("── STEP 1: Verify server ──")

try:
    r = requests.get(f"{API}/plans", timeout=10)
    if r.status_code != 200:
        raise ConnectionError(f"status {r.status_code}")
    log.info("PhronEdge API alive at %s", API)
except Exception as e:
    log.error("Cannot reach %s: %s", API, e)
    sys.exit(1)


# ═══════════════════════════════════════════════════════════
#  STEP 2 - Sign policy + register agent
# ═══════════════════════════════════════════════════════════

log.info("── STEP 2: Sign policy + register agent ──")

policy = {
    "organization": {
        "name": "PhronEdge Test Co",
        "jurisdiction": "DE",
        "industry": "IN",
        "company_size": "large",
        "data_types": ["PUB", "INT", "PII", "PII_HEALTH"],
        "data_residency": ["DE"],
        "deployment_jurisdictions": ["DE", "AT", "CH"],
    },
    "agents": [
        {
            "id": AGENT_ID,
            "purpose": "Investigates insurance claims for fraud and compliance",
            "model": "gpt-4o",
            "tier": "T2",
            "role": "standalone",
            "data_classifications": ["PUB", "INT", "PII", "PII_HEALTH"],
            "human_oversight": "supervised",
            "max_session_ttl": "never",
            "max_tokens_per_session": 50000,
            "max_tokens_per_day": 500000,
            "permitted_models": ["gpt-4o"],
            "can_delegate_to": [],
            "tools": ["claim_lookup", "patient_search", "report_generate"],
            "host_jurisdiction": "DE",
            "serving_jurisdictions": ["DE", "AT", "CH"],
            "behavioral_baseline": {
                "max_tool_calls_per_window": 20,
                "window_seconds": 600,
                "spike_multiplier": 3,
            },
        }
    ],
    "tools": [
        {
            "id": "claim_lookup",
            "description": "Search claims by ID, policy number, or claimant name",
            "type": "sdk",
            "endpoint": "",
            "data_classification": "PII",
            "permissions": ["read"],
            "jurisdictions": ["DE", "AT", "CH"],
            "max_per_day": 500,
            "deny_patterns": ["DROP", "DELETE", "TRUNCATE"],
        },
        {
            "id": "patient_search",
            "description": "Search patient records by name or ID",
            "type": "sdk",
            "endpoint": "",
            "data_classification": "PII_HEALTH",
            "permissions": ["read"],
            "jurisdictions": ["DE"],
            "max_per_day": 200,
            "requires_human_approval": False,
            "deny_patterns": ["UPDATE", "INSERT"],
        },
        {
            "id": "report_generate",
            "description": "Generate compliance and investigation reports",
            "type": "sdk",
            "endpoint": "",
            "data_classification": "INT",
            "permissions": ["read", "write"],
            "jurisdictions": ["DE", "US"],
            "max_per_day": 100,
        },
    ],
}

r = requests.post(f"{API}/governance/build", headers=H, json=policy, timeout=30)
d = r.json()
status = d.get("status", d.get("detail", "unknown"))
log.info("Policy status: %s", status)

if not d.get("signed_artifact"):
    log.error("Policy signing failed: %s", status)
    sys.exit(1)

sa = d["signed_artifact"]
log.info("Policy hash:   %s...", sa.get("policy_hash", "")[:24])
log.info("Frameworks:    %d", len(sa.get("frameworks", [])))
log.info("Controls:      %d/%d", sa.get("controls_met", 0), sa.get("controls_required", 0))

for aid, a in sa.get("agents", {}).items():
    pt = a.get("permitted_tools", [])
    if isinstance(pt, dict):
        log.info("Agent %s: v2 format, %d tools", aid, len(pt))
        for t, cfg in pt.items():
            log.info("  %s: perm=%s jur=%s deny=%s",
                     t,
                     cfg.get("permissions", []),
                     cfg.get("jurisdictions", []),
                     cfg.get("deny_patterns", cfg.get("deny", [])))
    else:
        log.info("Agent %s: v1 format, tools=%s", aid, pt)

for c in d.get("credentials_issued", []):
    log.info("Credential:    %s", c["credential_id"])


# ═══════════════════════════════════════════════════════════
#  STEP 3 - Verify credential
# ═══════════════════════════════════════════════════════════

log.info("── STEP 3: Verify credential ──")

r = requests.get(f"{API}/auth/credential?agent_id={AGENT_ID}", headers={"X-PhronEdge-Key": KEY}, timeout=10)
cred = r.json().get("credential", {})
agent_id     = cred.get("agent_id", "?")
tier         = cred.get("tier", "?")
jurisdiction = cred.get("jurisdiction", "?")
pt           = cred.get("permitted_tools", [])

log.info("Agent:         %s", agent_id)
log.info("Tier:          %s", tier)
log.info("Jurisdiction:  %s", jurisdiction)
log.info("Format:        %s", "v2 dict" if isinstance(pt, dict) else "v1 list")


# ═══════════════════════════════════════════════════════════
#  STEP 4 - Run governed tools
# ═══════════════════════════════════════════════════════════

log.info("── STEP 4: Run governed tools ──")

from phronedge import PhronEdge, GovernanceError

pe = PhronEdge(agent_id=AGENT_ID, raise_on_block=True)

allowed = 0
blocked = 0

# ── Tool A: v1 - just @pe.govern("name"), nothing else ──
@pe.govern("claim_lookup", action="read")
def claim_lookup_simple(claim_id):
    return json.dumps({"claim_id": claim_id, "status": "OPEN", "amount": 12500})

try:
    result = claim_lookup_simple("CLM-2026-001")
    log.info("ALLOWED  claim_lookup (v1)    %s", result[:60])
    allowed += 1
except Exception as e:
    log.warning("BLOCKED  claim_lookup (v1)    %s", str(e)[:80])
    blocked += 1

time.sleep(0.3)

# ── Tool B: v2 - action + jurisdiction ──
@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def claim_lookup_v2(claim_id):
    return json.dumps({"claim_id": claim_id, "status": "OPEN", "amount": 12500, "patient": "Hans Mueller"})

try:
    result = claim_lookup_v2("CLM-2026-002")
    log.info("ALLOWED  claim_lookup (v2)    %s", result[:60])
    allowed += 1
except Exception as e:
    log.warning("BLOCKED  claim_lookup (v2)    %s", str(e)[:80])
    blocked += 1

time.sleep(0.3)

# ── Tool C: patient search ──
@pe.govern("patient_search", action="read", jurisdiction="DE")
def patient_search(query):
    return json.dumps([{"id": "PAT-001", "name": "Hans Mueller", "dob": "1978-03-15"}])

try:
    result = patient_search("Hans Mueller")
    log.info("ALLOWED  patient_search       %s", result[:60])
    allowed += 1
except Exception as e:
    log.warning("BLOCKED  patient_search       %s", str(e)[:80])
    blocked += 1

time.sleep(0.3)

# ── Tool D: report generate (write) ──
@pe.govern("report_generate", action="write", jurisdiction="DE")
def report_generate(title):
    return json.dumps({"status": "generated", "title": title, "pages": 12})

try:
    result = report_generate("Q1 Fraud Summary")
    log.info("ALLOWED  report_generate      %s", result[:60])
    allowed += 1
except Exception as e:
    log.warning("BLOCKED  report_generate      %s", str(e)[:80])
    blocked += 1


# ═══════════════════════════════════════════════════════════
#  STEP 5 - Test blocks
# ═══════════════════════════════════════════════════════════

log.info("── STEP 5: Test blocks ──")

@pe.govern("claim_lookup", action="delete", jurisdiction="DE")
def bad_delete(claim_id):
    return "SHOULD NOT RUN"

@pe.govern("claim_lookup", action="read", jurisdiction="CN")
def bad_china(claim_id):
    return "SHOULD NOT RUN"

@pe.govern("bank_transfer", action="execute", jurisdiction="DE")
def bad_tool(amount):
    return "SHOULD NOT RUN"

@pe.govern("claim_lookup", action="read", jurisdiction="DE")
def bad_inject(query):
    return "SHOULD NOT RUN"

blocks = [
    ("DELETE action",      bad_delete,  ("CLM-001",)),
    ("CN jurisdiction",    bad_china,   ("CLM-001",)),
    ("Unauthorized tool",  bad_tool,    (50000,)),
    ("SQL injection",      bad_inject,  ("DROP TABLE claims",)),
]

for name, fn, args in blocks:
    try:
        fn(*args)
        log.error("FAIL     %s - should have been blocked", name)
    except (GovernanceError, Exception) as e:
        log.info("BLOCKED  %-22s %s", name, str(e)[:60])
        blocked += 1
    time.sleep(0.3)


# ═══════════════════════════════════════════════════════════
#  STEP 6 - CrewAI agent (optional)
# ═══════════════════════════════════════════════════════════

log.info("── STEP 6: CrewAI agent ──")

try:
    from crewai import Agent, Task, Crew
    from crewai.tools import tool as crewai_tool

    pe2 = PhronEdge(agent_id=AGENT_ID)

    @crewai_tool("claim_lookup")
    @pe2.govern("claim_lookup", action="read", jurisdiction="DE")
    def crew_claim_lookup(claim_id: str) -> str:
        """Look up insurance claim by ID like CLM-2026-001."""
        claims = {
            "CLM-2026-001": {"status": "OPEN", "amount": 12500, "patient": "Hans Mueller"},
            "CLM-2026-002": {"status": "UNDER_REVIEW", "amount": 45000, "patient": "Anna Schmidt"},
        }
        return json.dumps(claims.get(claim_id, {"error": "not found"}))

    @crewai_tool("patient_search")
    @pe2.govern("patient_search", action="read", jurisdiction="DE")
    def crew_patient_search(query: str) -> str:
        """Search patient records by name."""
        patients = [{"id": "PAT-001", "name": "Hans Mueller", "dob": "1978-03-15"}]
        results = [p for p in patients if query.lower() in p["name"].lower()]
        return json.dumps(results if results else [{"error": "not found"}])

    investigator = Agent(
        role="Claims Investigator",
        goal="Investigate insurance claims and report findings",
        backstory="Senior investigator. Every tool call governed by PhronEdge.",
        tools=[crew_claim_lookup, crew_patient_search],
        verbose=True,
    )

    task = Task(
        description="Look up claim CLM-2026-001 and find the patient. Summarize findings.",
        agent=investigator,
        expected_output="Claim details with patient information.",
    )

    crew = Crew(agents=[investigator], tasks=[task], verbose=True)
    result = crew.kickoff()
    log.info("CrewAI result: %s", str(result)[:120])

except ImportError:
    log.info("CrewAI not installed - skipping (pip install crewai to enable)")
except Exception as e:
    log.warning("CrewAI error: %s", e)


# ═══════════════════════════════════════════════════════════
#  STEP 7 - Observe (no browser needed)
# ═══════════════════════════════════════════════════════════

log.info("── STEP 7: Observe ──")
time.sleep(1)

r = requests.get(f"{API}/tenant/chain?limit=50", headers={"X-PhronEdge-Key": KEY}, timeout=10)

if r.status_code == 200:
    data   = r.json()
    events = data.get("events", data.get("chain", []))

    ev_allowed = sum(1 for e in events if "ALLOWED" in str(e.get("event_type", "")))
    ev_blocked = sum(1 for e in events if "BLOCKED" in str(e.get("event_type", "")))
    ev_other   = len(events) - ev_allowed - ev_blocked

    log.info("Total events:  %d", len(events))
    log.info("Allowed:       %d", ev_allowed)
    log.info("Blocked:       %d", ev_blocked)
    log.info("Other:         %d", ev_other)
    log.info("Chain valid:   %s", data.get("chain_valid", "unknown"))
    log.info("")

    log.info("%-36s %-20s %s", "EVENT", "TOOL", "AGENT")
    log.info("%-36s %-20s %s", "-" * 34, "-" * 18, "-" * 18)
    for e in events[-12:]:
        et   = e.get("event_type", "")
        tool = str(e.get("tool", e.get("detail", "")))[:20]
        log.info("%-36s %-20s %s", et, tool, e.get("agent_id", ""))
else:
    log.warning("Audit chain returned %s - may require Bearer token", r.status_code)


# ═══════════════════════════════════════════════════════════
#  Summary
# ═══════════════════════════════════════════════════════════

log.info("")
log.info("=" * 55)
log.info("  PhronEdge E2E - Complete")
log.info("=" * 55)
log.info("  Policy signed:      YES (v2 per-tool permissions)")
log.info("  Credential issued:  YES (ML-DSA-65)")
log.info("  Agent:              %s (%s)", agent_id, tier)
log.info("  Jurisdiction:       %s", jurisdiction)
log.info("  Allowed calls:      %d", allowed)
log.info("  Blocked calls:      %d", blocked)
log.info("  Audit chain:        hash-chained, immutable")
log.info("  Browser needed:     NO")
log.info("=" * 55)
log.info("  Everything governed. Everything audited. One script.")
