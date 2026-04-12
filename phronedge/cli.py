"""
PhronEdge CLI

Usage:
  phronedge scan <file>                    Scan agent code for ungoverned tools
  phronedge verify [--agent <id>]          Verify credential and gateway connection
  phronedge export <format> [--agent <id>] Export signed policy (rego, yaml, json)
"""

import sys
import os
import ast
import json
import argparse
import requests


def main():
    parser = argparse.ArgumentParser(
        prog="phronedge",
        description="PhronEdge CLI - Constitutional governance for AI agents",
    )
    sub = parser.add_subparsers(dest="command")

    # scan
    scan_parser = sub.add_parser("scan", help="Scan agent code for ungoverned tools")
    scan_parser.add_argument("file", help="Python file to scan")
    scan_parser.add_argument("--strict", action="store_true", help="Exit 1 if ungoverned tools found")

    # verify
    verify_parser = sub.add_parser("verify", help="Verify credential and gateway connection")
    verify_parser.add_argument("--agent", help="Agent ID to verify (default: first available)")

    # export
    export_parser = sub.add_parser("export", help="Export signed policy")
    export_parser.add_argument("format", choices=["rego", "yaml", "json"], help="Export format")
    export_parser.add_argument("-o", "--output", help="Output file path")
    export_parser.add_argument("--agent", help="Agent ID to export (default: first available)")

    args = parser.parse_args()

    if args.command == "scan":
        cmd_scan(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "export":
        cmd_export(args)
    else:
        parser.print_help()


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
            func_name = node.name
            if func_name.startswith("_"):
                continue  # skip private functions

            # Check if any decorator is pe.govern or @pe.govern("name")
            is_governed = False
            govern_name = ""

            for dec in node.decorator_list:
                dec_src = ast.dump(dec)
                if "govern" in dec_src:
                    is_governed = True
                    # Extract the tool name from @pe.govern("tool_name")
                    if isinstance(dec, ast.Call) and dec.args:
                        if isinstance(dec.args[0], ast.Constant):
                            govern_name = dec.args[0].value
                    break

            # Check if function looks like a tool (has docstring, not a helper)
            has_docstring = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )

            # Also check for framework decorators (@tool, @agent.tool, etc.)
            has_tool_decorator = False
            for dec in node.decorator_list:
                dec_src = ast.dump(dec)
                if "tool" in dec_src.lower():
                    has_tool_decorator = True
                    break

            is_tool = has_docstring or has_tool_decorator

            if is_tool or is_governed:
                info = {
                    "name": func_name,
                    "line": node.lineno,
                    "governed": is_governed,
                    "govern_name": govern_name,
                    "has_docstring": has_docstring,
                    "has_tool_decorator": has_tool_decorator,
                }
                all_functions.append(info)
                if is_governed:
                    governed.append(info)
                else:
                    ungoverned.append(info)

    # Output
    print(f"\nPhronEdge Scan: {filepath}")
    print(f"{'=' * 50}")
    print()

    if not all_functions:
        print("No tool functions found.")
        print("Tools are functions with docstrings or @tool decorators.")
        return

    for fn in all_functions:
        status = "governed" if fn["governed"] else "NOT governed"
        icon = "+" if fn["governed"] else "x"
        name_display = fn["name"]
        if fn["govern_name"]:
            name_display = f'{fn["name"]} (as "{fn["govern_name"]}")'
        print(f"  [{icon}] {name_display:40s} line {fn['line']:4d}  {status}")

    print()
    print(f"Total: {len(all_functions)} tools")
    print(f"  Governed:   {len(governed)}")
    print(f"  Ungoverned: {len(ungoverned)}")

    if ungoverned:
        print()
        print("Ungoverned tools execute without governance.")
        print("Add @pe.govern(\"tool_name\") to each one.")
        if args.strict:
            sys.exit(1)
    else:
        print()
        print("All tools governed.")


def cmd_verify(args):
    """Verify API key, credential, and gateway connection."""
    api_key = os.getenv("PHRONEDGE_API_KEY", "")
    gateway = os.getenv("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")

    print(f"\nPhronEdge Verify")
    print(f"{'=' * 50}")
    print()

    # Check API key
    if not api_key:
        print("[x] PHRONEDGE_API_KEY not set")
        print("    Run: export PHRONEDGE_API_KEY=pe_live_your_key")
        sys.exit(1)
    else:
        masked = api_key[:10] + "*" * (len(api_key) - 14) + api_key[-4:]
        print(f"[+] API key: {masked}")

    # Check gateway
    print(f"[+] Gateway: {gateway}")
    print()

    # Test connection
    print("Testing gateway connection...")
    try:
        r = requests.get(f"{gateway}/plans", timeout=10)
        if r.status_code == 200:
            plans = r.json().get("plans", {})
            print(f"[+] Gateway reachable. {len(plans)} plans available.")
        else:
            print(f"[x] Gateway returned {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"[x] Gateway unreachable: {e}")
        sys.exit(1)

    # Test credential fetch
    print()
    print("Fetching credential...")
    try:
        r = requests.get(
            f"{gateway}/auth/credential",
            headers={"X-PhronEdge-Key": api_key},
            params={"agent_id": args.agent} if args.agent else {},
            timeout=10,
        )
        if r.status_code == 200:
            cred = r.json()
            agent_id = cred.get("credential", {}).get("agent_id", cred.get("agent_id", ""))
            jurisdiction = cred.get("credential", {}).get("jurisdiction", cred.get("jurisdiction", ""))
            tools = cred.get("credential", {}).get("permitted_tools", cred.get("permitted_tools", []))
            print(f"[+] Credential valid")
            print(f"    Agent:        {agent_id}")
            print(f"    Jurisdiction: {jurisdiction}")
            print(f"    Tools:        {', '.join(tools) if tools else 'none'}")
            print()
            print("Ready. Your agent is governed.")
        else:
            print(f"[x] Credential fetch failed: {r.status_code}")
            try:
                detail = r.json().get("detail", "")
                if detail:
                    print(f"    {detail}")
            except Exception:
                pass
            sys.exit(1)
    except Exception as e:
        print(f"[x] Credential fetch failed: {e}")
        sys.exit(1)


def cmd_export(args):
    """Export the signed policy."""
    api_key = os.getenv("PHRONEDGE_API_KEY", "")
    gateway = os.getenv("PHRONEDGE_GATEWAY_URL", "https://api.phronedge.com/api/v1")

    if not api_key:
        print("PHRONEDGE_API_KEY not set")
        sys.exit(1)

    fmt = args.format
    print(f"\nExporting policy as {fmt}...")

    try:
        r = requests.get(
            f"{gateway}/policy/export/{fmt}",
            headers={"X-PhronEdge-Key": api_key},
            params={"agent_id": args.agent} if args.agent else {},
            timeout=15,
        )

        if r.status_code == 200:
            data = r.json()

            if fmt == "rego":
                content = data.get("rego", "")
            elif fmt == "yaml":
                content = data.get("yaml", "")
            else:
                content = json.dumps(data.get("policy", data), indent=2)

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
            print("No signed policy found. Sign a policy in the console first.")
            print("https://phronedge.com/brain")
            sys.exit(1)
        else:
            print(f"Export failed: {r.status_code}")
            sys.exit(1)

    except Exception as e:
        print(f"Export failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
