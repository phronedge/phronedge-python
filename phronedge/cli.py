"""
PhronEdge CLI

Usage:
  phronedge scan <file>                    Scan agent code for ungoverned tools
  phronedge verify [--agent <id>]          Verify credential and gateway connection
  phronedge export <format> [--agent <id>] Export signed policy (rego, yaml, json)

  phronedge policy build <file>            Build policy from YAML (preview only)
  phronedge policy deploy <file>           Build + deploy policy (issues credentials)
  phronedge policy status                  Show signed policy and agent status

  phronedge agent list                     List all governed agents
  phronedge agent quarantine <id> <reason> Quarantine an agent
  phronedge agent reinstate <id> <reason>  Reinstate a quarantined agent

  phronedge chain verify                   Verify hash chain integrity
  phronedge chain events [--limit N]       Show recent chain events
"""

import sys
import os
import ast
import json
import argparse
import requests


def _get_config():
    """Read API key and gateway URL from env."""
    api_key = os.getenv("PHRONEDGE_API_KEY", "")
    gateway = os.getenv("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")
    return api_key, gateway


def _headers(api_key):
    return {
        "X-PhronEdge-Key": api_key,
        "Content-Type": "application/json",
        "User-Agent": "phronedge-cli/2.4.7",
    }


def _require_key():
    api_key, gateway = _get_config()
    if not api_key:
        print("[x] PHRONEDGE_API_KEY not set")
        print("    Run: export PHRONEDGE_API_KEY=pe_live_your_key")
        sys.exit(1)
    return api_key, gateway


def main():
    from phronedge import __version__
    parser = argparse.ArgumentParser(
        prog="phronedge",
        description="PhronEdge CLI - Constitutional governance for AI agents",
    )
    parser.add_argument("--version", action="version", version=f"phronedge {__version__}")
    sub = parser.add_subparsers(dest="command")

    # scan
    scan_p = sub.add_parser("scan", help="Scan agent code for ungoverned tools")
    scan_p.add_argument("file", help="Python file to scan")
    scan_p.add_argument("--strict", action="store_true", help="Exit 1 if ungoverned tools found")

    # verify
    verify_p = sub.add_parser("verify", help="Verify credential and gateway connection")
    verify_p.add_argument("--agent", help="Agent ID to verify")

    # export
    export_p = sub.add_parser("export", help="Export signed policy")
    export_p.add_argument("format", choices=["rego", "yaml", "json"], help="Export format")
    export_p.add_argument("-o", "--output", help="Output file path")
    export_p.add_argument("--agent", help="Agent ID")

    # policy
    policy_p = sub.add_parser("policy", help="Policy management")
    policy_sub = policy_p.add_subparsers(dest="policy_command")
    pb = policy_sub.add_parser("build", help="Build policy (preview, no deploy)")
    pb.add_argument("file", nargs="?", help="Policy YAML file")
    pb.add_argument("--json", dest="json_input", action="store_true", help="Input is JSON")
    pd = policy_sub.add_parser("deploy", help="Build + deploy policy (issues credentials)")
    pd.add_argument("file", nargs="?", help="Policy YAML file")
    pd.add_argument("--json", dest="json_input", action="store_true", help="Input is JSON")
    policy_sub.add_parser("status", help="Show policy and agent status")

    # agent
    agent_p = sub.add_parser("agent", help="Agent lifecycle management")
    agent_sub = agent_p.add_subparsers(dest="agent_command")
    agent_sub.add_parser("list", help="List all governed agents")
    aq = agent_sub.add_parser("quarantine", help="Quarantine an agent")
    aq.add_argument("id", help="Agent ID")
    aq.add_argument("reason", help="Quarantine reason")
    ar = agent_sub.add_parser("reinstate", help="Reinstate a quarantined agent")
    ar.add_argument("id", help="Agent ID")
    ar.add_argument("reason", help="Reinstatement reason")

    # chain
    chain_p = sub.add_parser("chain", help="Hash chain operations")
    chain_sub = chain_p.add_subparsers(dest="chain_command")
    chain_sub.add_parser("verify", help="Verify chain integrity")
    ce = chain_sub.add_parser("events", help="Show recent events")
    ce.add_argument("--limit", type=int, default=20, help="Number of events")

    args = parser.parse_args()

    commands = {
        "scan": cmd_scan,
        "verify": cmd_verify,
        "export": cmd_export,
    }

    if args.command in commands:
        commands[args.command](args)
    elif args.command == "policy":
        if args.policy_command == "build":
            cmd_policy_build(args, deploy=False)
        elif args.policy_command == "deploy":
            cmd_policy_build(args, deploy=True)
        elif args.policy_command == "status":
            cmd_policy_status(args)
        else:
            policy_p.print_help()
    elif args.command == "agent":
        if args.agent_command == "list":
            cmd_agent_list(args)
        elif args.agent_command == "quarantine":
            cmd_agent_quarantine(args)
        elif args.agent_command == "reinstate":
            cmd_agent_reinstate(args)
        else:
            agent_p.print_help()
    elif args.command == "chain":
        if args.chain_command == "verify":
            cmd_chain_verify(args)
        elif args.chain_command == "events":
            cmd_chain_events(args)
        else:
            chain_p.print_help()
    else:
        parser.print_help()


# ================================================================
# SCAN
# ================================================================

def cmd_scan(args):
    """Scan a Python file for tool functions and check which are governed."""
    filepath = args.file
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r") as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"Syntax error in {filepath}: {e}")
        sys.exit(1)

    governed = []
    ungoverned = []
    all_functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name.startswith("_"):
                continue

            is_governed = False
            govern_name = ""
            for dec in node.decorator_list:
                if "govern" in ast.dump(dec):
                    is_governed = True
                    if isinstance(dec, ast.Call) and dec.args:
                        if isinstance(dec.args[0], ast.Constant):
                            govern_name = dec.args[0].value
                    break

            has_docstring = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            has_tool_decorator = any("tool" in ast.dump(d).lower() for d in node.decorator_list)

            if has_docstring or has_tool_decorator or is_governed:
                info = {"name": node.name, "line": node.lineno, "governed": is_governed, "govern_name": govern_name}
                all_functions.append(info)
                (governed if is_governed else ungoverned).append(info)

    print(f"\nPhronEdge Scan: {filepath}")
    print(f"{'=' * 50}")
    print()

    if not all_functions:
        print("No tool functions found.")
        return

    for fn in all_functions:
        icon = "+" if fn["governed"] else "x"
        status = "governed" if fn["governed"] else "NOT governed"
        name = f'{fn["name"]} (as "{fn["govern_name"]}")' if fn["govern_name"] else fn["name"]
        print(f"  [{icon}] {name:40s} line {fn['line']:4d}  {status}")

    print(f"\nTotal: {len(all_functions)} tools")
    print(f"  Governed:   {len(governed)}")
    print(f"  Ungoverned: {len(ungoverned)}")

    if ungoverned:
        print("\nUngoverned tools execute without governance.")
        print('Add @pe.govern("tool_name") to each one.')
        if args.strict:
            sys.exit(1)
    else:
        print("\nAll tools governed.")


# ================================================================
# VERIFY
# ================================================================

def cmd_verify(args):
    """Verify API key, credential, and gateway connection."""
    api_key, gateway = _require_key()

    print(f"\nPhronEdge Verify")
    print(f"{'=' * 50}")
    print()

    masked = api_key[:10] + "*" * max(len(api_key) - 14, 4) + api_key[-4:]
    print(f"[+] API key: {masked}")
    print(f"[+] Gateway: {gateway}")
    print()

    # Health check
    print("Testing gateway connection...")
    try:
        base = gateway.rstrip("/").rsplit("/api/v1", 1)[0]
        r = requests.get(f"{base}/healthz", timeout=10)
        if r.status_code == 200:
            print(f"[+] Gateway reachable. Status: {r.json().get('status', 'ok')}")
        else:
            print(f"[x] Gateway returned {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"[x] Gateway unreachable: {e}")
        sys.exit(1)

    print()

    if not args.agent:
        # No agent specified — list all agents so user knows what to verify
        print("No --agent specified. Listing available agents:")
        print()
        try:
            r = requests.get(f"{gateway}/tenant/agents", headers=_headers(api_key), timeout=10)
            if r.status_code == 200:
                agents = r.json().get("agents", [])
                if not agents:
                    print("  No agents found. Sign and deploy a policy first.")
                    print("  https://phronedge.com/brain")
                    return
                for a in agents:
                    aid = a.get("agent_id", "")
                    state = a.get("state", "ACTIVE")
                    tier = a.get("tier", "")
                    icon = "+" if state == "ACTIVE" else "!" if state == "QUARANTINED" else "x"
                    print(f"  [{icon}] {aid:30s} {tier:4s} {state}")
                print()
                print(f"Run: phronedge verify --agent <agent_id>")
            else:
                print(f"  [x] Agent list failed: {r.status_code}")
        except Exception as e:
            print(f"  [x] Agent list failed: {e}")
        return

    # Specific agent — fetch and verify credential
    print(f"Verifying agent: {args.agent}")
    try:
        r = requests.get(
            f"{gateway}/auth/credential",
            headers=_headers(api_key),
            params={"agent_id": args.agent},
            timeout=10,
        )
        if r.status_code == 200:
            cred = r.json()
            c = cred.get("credential", cred)
            returned_agent = c.get("agent_id", "")
            # Defensive: verify server returned the agent we asked for
            if returned_agent != args.agent:
                print(f"[x] Requested agent '{args.agent}' but server returned '{returned_agent}'")
                print(f"    Agent '{args.agent}' may not exist. Check: phronedge agent list")
                sys.exit(1)
            tools = c.get("permitted_tools", [])
            if isinstance(tools, dict):
                tools = list(tools.keys())
            print(f"[+] Credential valid")
            print(f"    Agent:        {c.get('agent_id', '')}")
            print(f"    Tier:         {c.get('tier', '')}")
            print(f"    Jurisdiction: {c.get('jurisdiction', '')}")
            print(f"    Tools:        {', '.join(tools) if tools else 'none'}")
            sig = c.get("phronedge_signature", "")
            if isinstance(sig, dict):
                print(f"    Signed:       {sig.get('algorithm', '')} key={sig.get('key_id', '')}")
            print()
            print(f"Ready. Agent '{args.agent}' is governed.")
        else:
            print(f"[x] Credential fetch failed: {r.status_code}")
            try:
                print(f"    {r.json().get('detail', '')}")
            except Exception:
                pass
            sys.exit(1)
    except Exception as e:
        print(f"[x] Credential fetch failed: {e}")
        sys.exit(1)


# ================================================================
# EXPORT
# ================================================================

def cmd_export(args):
    """Export the signed policy."""
    api_key, gateway = _require_key()
    fmt = args.format

    if not args.agent:
        print("\n[x] --agent is required. Which agent's policy do you want to export?")
        print()
        try:
            r = requests.get(f"{gateway}/tenant/agents", headers=_headers(api_key), timeout=10)
            if r.status_code == 200:
                agents = r.json().get("agents", [])
                for a in agents:
                    print(f"  {a.get('agent_id', '')}")
                print()
                print(f"Run: phronedge export {fmt} --agent <agent_id>")
        except Exception:
            pass
        sys.exit(1)

    print(f"\nExporting policy for {args.agent} as {fmt}...")

    try:
        params = {"agent_id": args.agent}
        r = requests.get(f"{gateway}/policy/export/{fmt}", headers=_headers(api_key), params=params, timeout=15)

        if r.status_code == 200:
            data = r.json()
            content = data.get("rego", "") if fmt == "rego" else data.get("yaml", "") if fmt == "yaml" else json.dumps(data.get("policy", data), indent=2)

            if args.output:
                with open(args.output, "w") as f:
                    f.write(content)
                print(f"Exported to {args.output}")
                print(f"Policy hash: {data.get('policy_hash', '')}")
            else:
                print()
                print(content)
        elif r.status_code == 401:
            print("Authentication required. Check your PHRONEDGE_API_KEY.")
            sys.exit(1)
        elif r.status_code == 404:
            print("No signed policy found. Sign a policy first: https://phronedge.com/brain")
            sys.exit(1)
        else:
            print(f"Export failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Export failed: {e}")
        sys.exit(1)


# ================================================================
# POLICY BUILD / DEPLOY
# ================================================================

def cmd_policy_build(args, deploy=False):
    """Build or deploy a policy."""
    api_key, gateway = _require_key()
    action = "Deploy" if deploy else "Build"

    if args.file:
        if not os.path.exists(args.file):
            print(f"File not found: {args.file}")
            sys.exit(1)
        with open(args.file) as f:
            content = f.read()
    else:
        if sys.stdin.isatty():
            print(f"Usage: phronedge policy {action.lower()} <file>")
            sys.exit(1)
        content = sys.stdin.read()

    if args.json_input or content.strip().startswith("{"):
        try:
            policy_data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON: {e}")
            sys.exit(1)
    else:
        try:
            import yaml
            policy_data = yaml.safe_load(content)
        except ImportError:
            print("PyYAML required for YAML input: pip install pyyaml")
            sys.exit(1)
        except Exception as e:
            print(f"Invalid YAML: {e}")
            sys.exit(1)

    policy_data["deploy"] = deploy

    print(f"\nPhronEdge Policy {action}")
    print(f"{'=' * 50}")
    print()

    try:
        r = requests.post(f"{gateway}/governance/build", json=policy_data, headers=_headers(api_key), timeout=30)

        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "")
            artifact = data.get("signed_artifact", {})

            print(f"[+] Policy: {status.upper()}")
            print(f"    Hash:       {artifact.get('policy_hash', '')[:16]}...")
            print(f"    Frameworks: {len(artifact.get('frameworks', []))}")
            print(f"    Controls:   {artifact.get('controls_met', 0)}/{artifact.get('controls_required', 0)}")
            print(f"    Agents:     {len(artifact.get('agents', {}))}")
            print(f"    Tools:      {len(artifact.get('tools', {}))}")

            if deploy:
                creds = data.get("credentials_issued", [])
                print(f"\n    Deployed: {len(creds)} credential(s) issued")
                for c in creds:
                    print(f"      {c.get('agent_id', '')}: {c.get('credential_id', '')}")
            else:
                print("\n    Preview only. Run 'phronedge policy deploy' to issue credentials.")
        elif r.status_code == 422:
            print(f"[x] Validation error: {r.json().get('detail', '')}")
            sys.exit(1)
        else:
            print(f"[x] {action} failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"{action} failed: {e}")
        sys.exit(1)


# ================================================================
# POLICY STATUS
# ================================================================

def cmd_policy_status(args):
    """Show current policy and agent status."""
    api_key, gateway = _require_key()

    print(f"\nPhronEdge Policy Status")
    print(f"{'=' * 50}")
    print()

    try:
        r = requests.get(f"{gateway}/governance/registry", headers=_headers(api_key), timeout=10)
        if r.status_code == 200:
            data = r.json()
            agents = data.get("agents", [])
            tools = data.get("tools", [])

            print(f"Agents: {len(agents)}")
            for a in agents:
                aid = a.get("agent_id", a.get("id", ""))
                tier = a.get("tier", "")
                state = a.get("state", "ACTIVE")
                icon = "+" if state == "ACTIVE" else "!" if state == "QUARANTINED" else "x"
                print(f"  [{icon}] {aid:30s} {tier:4s} {state}")

            print(f"\nTools: {len(tools)}")
            for t in tools[:10]:
                tid = t.get("id", t.get("tool_id", ""))
                print(f"  [+] {tid}")
        else:
            print(f"[x] Status fetch failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Status failed: {e}")
        sys.exit(1)


# ================================================================
# AGENT LIST / QUARANTINE / REINSTATE
# ================================================================

def cmd_agent_list(args):
    """List all governed agents."""
    api_key, gateway = _require_key()

    print(f"\nPhronEdge Agents")
    print(f"{'=' * 50}")
    print()

    try:
        r = requests.get(f"{gateway}/tenant/agents", headers=_headers(api_key), timeout=10)
        if r.status_code == 200:
            agents = r.json().get("agents", [])
            if not agents:
                print("No agents found. Deploy a policy first: https://phronedge.com/brain")
                return
            for a in agents:
                aid = a.get("agent_id", "")
                state = a.get("state", "ACTIVE")
                tier = a.get("tier", "")
                tools = a.get("tools", [])
                tc = len(tools) if isinstance(tools, (list, dict)) else 0
                icon = "+" if state == "ACTIVE" else "!" if state == "QUARANTINED" else "x"
                print(f"  [{icon}] {aid}")
                print(f"      Tier: {tier}  Tools: {tc}  State: {state}")
        else:
            print(f"[x] Failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


def cmd_agent_quarantine(args):
    """Quarantine an agent."""
    api_key, gateway = _require_key()
    print(f"\nQuarantining agent: {args.id}")

    try:
        r = requests.post(
            f"{gateway}/agent/{args.id}/quarantine",
            json={"reason": args.reason, "initiated_by": "cli"},
            headers=_headers(api_key), timeout=10,
        )
        if r.status_code == 200:
            print(f"[+] Agent {args.id} quarantined. All tool calls blocked.")
        else:
            print(f"[x] Failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


def cmd_agent_reinstate(args):
    """Reinstate a quarantined agent."""
    api_key, gateway = _require_key()
    print(f"\nReinstating agent: {args.id}")

    try:
        r = requests.post(
            f"{gateway}/agent/{args.id}/reinstate",
            json={"reason": args.reason, "initiated_by": "cli"},
            headers=_headers(api_key), timeout=10,
        )
        if r.status_code == 200:
            print(f"[+] Agent {args.id} reinstated. Tool calls resumed.")
        else:
            print(f"[x] Failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


# ================================================================
# CHAIN VERIFY / EVENTS
# ================================================================

def cmd_chain_verify(args):
    """Verify hash chain integrity."""
    api_key, gateway = _require_key()

    print(f"\nPhronEdge Chain Verification")
    print(f"{'=' * 50}")
    print()

    try:
        r = requests.get(f"{gateway}/tenant/chain?limit=200", headers=_headers(api_key), timeout=15)
        if r.status_code == 200:
            data = r.json()
            valid = data.get("chain_valid", False)
            length = data.get("chain_length", 0)
            events = data.get("events", [])
            stats = data.get("stats", {})

            icon = "+" if valid else "x"
            print(f"  [{icon}] Chain valid: {valid}")
            print(f"      Events:     {length}")
            print(f"      Allowed:    {stats.get('allowed', 0)}")
            print(f"      Blocked:    {stats.get('blocked', 0)}")
            print(f"      PII:        {stats.get('pii', 0)}")
            print(f"      Tamper:     {stats.get('tamper', 0)}")

            if events:
                ts = events[0].get("created_at", 0)
                if isinstance(ts, (int, float)):
                    from datetime import datetime
                    ts = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    ts = str(ts)[:23]
                print(f"\n  Latest: {events[0].get('event_type', '')} ({ts})")

            if not valid:
                print("\n  [!] Chain integrity broken.")
                sys.exit(1)
            else:
                print("\n  Chain is intact. All events verified.")
        else:
            print(f"[x] Failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


def cmd_chain_events(args):
    """Show recent chain events."""
    api_key, gateway = _require_key()

    try:
        r = requests.get(f"{gateway}/tenant/chain?limit={args.limit}", headers=_headers(api_key), timeout=10)
        if r.status_code == 200:
            events = r.json().get("events", [])

            print(f"\nPhronEdge Chain Events (latest {len(events)})")
            print(f"{'=' * 80}")
            print(f"\n  {'TIME':<24s} {'EVENT':<28s} {'AGENT':<20s} {'RESULT'}")
            print(f"  {'-'*23} {'-'*27} {'-'*19} {'-'*6}")

            for e in events:
                ts = e.get("created_at", 0)
                if isinstance(ts, (int, float)):
                    from datetime import datetime
                    ts = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    ts = str(ts)[:23]
                etype = e.get("event_type", "")
                agent = e.get("agent_id", "system")
                ok = "OK" if e.get("hash") else "--"
                print(f"  {ts:<23s} {etype:<28s} {agent:<20s} {ok}")
        else:
            print(f"[x] Failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
