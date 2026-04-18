"""
PhronEdge SDK  - thin governance client.

Does 3 things:
  1. Authenticate with API key
  2. Wrap functions with @pe.govern
  3. Route tool calls through the gateway

Everything else lives on the server.
"""

import os
import json
import time
import logging
import functools
import inspect
from typing import Optional, Callable, Any

import requests

logger = logging.getLogger("phronedge")

DEFAULT_GATEWAY = "https://api.phronedge.com/api/v1"


class GovernanceError(Exception):
    """Base PhronEdge governance error."""
    def __init__(self, message, checkpoint="", regulation=""):
        super().__init__(message)
        self.reason = message
        self.checkpoint = checkpoint
        self.regulation = regulation
        self.blocked = False
        self.retry = False


class ToolBlocked(GovernanceError):
    """Tool call blocked. Temporary  - may be retried."""
    def __init__(self, message, checkpoint="", regulation="", retry=True):
        super().__init__(message, checkpoint, regulation)
        self.blocked = True
        self.retry = retry


class AgentTerminated(GovernanceError):
    """Agent permanently killed."""
    def __init__(self, message="Agent has been permanently terminated"):
        super().__init__(message)
        self.blocked = True
        self.retry = False


class PhronEdge:
    """
    PhronEdge governance client.

    Setup:
        .env:
        PHRONEDGE_API_KEY=pe_live_xxxxxxxxx

    Usage:
        from phronedge import PhronEdge

        pe = PhronEdge()

        @pe.govern("lookup_claim")
        def lookup_claim(claim_id: str) -> str:
            return db.query(claim_id)

        result = lookup_claim("CLM-001")  # governed by PhronEdge
    """

    def __init__(self, api_key=None, gateway_url=None, timeout=30, raise_on_block=False, agent_id=None):
        self.api_key = api_key or os.getenv("PHRONEDGE_API_KEY", "")
        self.gateway_url = gateway_url or os.getenv("PHRONEDGE_GATEWAY_URL", "") or DEFAULT_GATEWAY
        self.timeout = timeout
        self.raise_on_block = raise_on_block

        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "X-PhronEdge-Key": self.api_key,
            "User-Agent": "phronedge-sdk/2.4.6",
        })

        # Credential cache
        self._credential = None
        self._credential_ts = 0
        self._agent_id = agent_id or os.getenv("PHRONEDGE_AGENT_ID", "")

        if not self.api_key:
            logger.warning("No PHRONEDGE_API_KEY set. Set it in your .env or pass api_key= to PhronEdge().")

        if not self._agent_id:
            logger.warning(
                "No agent_id set. Set PHRONEDGE_AGENT_ID env var or pass agent_id= to PhronEdge(). "
                "Without it, the first available credential is used — unreliable with multiple agents."
            )

    def govern(self, tool_name=None, action='execute', jurisdiction=None, mcp=None, delegates=None):
        """
        Decorator  - wraps a function with constitutional governance.

            @pe.govern("lookup_claim")
            def lookup_claim(claim_id: str) -> str:
                return db.query(claim_id)

        Or without name (uses function name):

            @pe.govern()
            def lookup_claim(claim_id: str) -> str:
                return db.query(claim_id)
        """
        def decorator(func):
            name = tool_name or func.__name__

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return self._governed_call(name, func, args, kwargs, _action=action, _jurisdiction=jurisdiction, _mcp=mcp, _delegates=delegates)

            wrapper._phronedge_governed = True
            wrapper._phronedge_tool_name = name
            return wrapper
        return decorator

    def _governed_call(self, tool_name, func, args, kwargs, _action='execute', _jurisdiction=None, _mcp=None, _delegates=None):
        """Execute a governed tool call."""
        self._ensure_credential()

        # Build arguments dict
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        arguments = dict(bound.arguments)

        # Call gateway
        try:
            r = self._call_gateway(tool_name, arguments, action=_action, jurisdiction=_jurisdiction, mcp=_mcp, delegates=_delegates)
        except requests.ConnectionError:
            raise GovernanceError(f"PhronEdge gateway unreachable at {self.gateway_url}")
        except Exception as e:
            raise GovernanceError(f"Gateway error: {e}")

        if r.status_code == 200:
            return func(*args, **kwargs)

        elif r.status_code == 403:
            detail = self._parse_detail(r)
            reason = detail.get("reason", "Blocked by governance")
            checkpoint = detail.get("checkpoint", "")
            regulation = detail.get("regulation", "")
            error = detail.get("error", "")
            retry = "quarantined" not in error

            if "killed" in error or "terminated" in error:
                raise AgentTerminated(reason)

            if self.raise_on_block:
                raise ToolBlocked(reason, checkpoint=checkpoint, regulation=regulation, retry=retry)

            return {
                "blocked": True,
                "reason": reason,
                "checkpoint": checkpoint,
                "regulation": regulation,
                "retry": retry,
                "message": "Tool call blocked by PhronEdge governance.",
            }

        elif r.status_code == 401:
            raise GovernanceError("Invalid API key. Check your PHRONEDGE_API_KEY.")

        else:
            raise GovernanceError(f"Gateway returned {r.status_code}")

    def _call_gateway(self, tool_name, arguments, action='execute', jurisdiction=None, mcp=None, delegates=None):
        """Send tool call to gateway with v2 params."""
        cred_json = json.dumps(self._credential or {})
        payload = {"arguments": arguments, "action": action}
        if jurisdiction:
            payload["jurisdiction"] = jurisdiction
        if mcp:
            payload["mcp"] = mcp
        if delegates:
            payload["delegates"] = delegates
        return self._session.post(
            f"{self.gateway_url}/gateway/proxy/{tool_name}",
            json=payload,
            headers={"X-Constitutional-Credential": cred_json},
            timeout=self.timeout,
        )

    def _ensure_credential(self):
        """Fetch credential from gateway if expired or missing."""
        if self._credential and (time.time() - self._credential_ts) < 300:
            return
        try:
            params = {"agent_id": self._agent_id} if self._agent_id else {}
            r = self._session.get(f"{self.gateway_url}/auth/credential", params=params, timeout=self.timeout)
            if r.status_code == 200:
                data = r.json()
                self._credential = data.get("credential", data)
                self._agent_id = data.get("agent_id", "")
                self._credential_ts = time.time()
        except Exception as e:
            logger.warning("Credential fetch failed: %s", e)

    def _parse_detail(self, r):
        try:
            detail = r.json().get("detail", {})
            return detail if isinstance(detail, dict) else {"reason": str(detail)}
        except:
            return {"reason": r.text[:200]}

    # -- Utility methods --

    def scan(self, text):
        """Pre-scan text for PII or prompt injection."""
        try:
            r = self._session.post(f"{self.gateway_url}/gateway/scan", json={"text": text}, timeout=self.timeout)
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    def status(self):
        """Check gateway status."""
        try:
            r = self._session.get(f"{self.gateway_url}/gateway/status", timeout=self.timeout)
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    # -- Agent Lifecycle --

    def quarantine(self, reason=""):
        """
        Quarantine the agent. All tool calls blocked immediately.
        No restart needed. No code change.
        """
        self._ensure_credential()
        agent_id = self._agent_id or self._credential.get("agent_id", "")
        if not agent_id:
            raise GovernanceError("No agent_id available. Fetch credential first.")
        try:
            r = self._session.post(
                f"{self.gateway_url}/agent/{agent_id}/quarantine",
                json={"reason": reason},
                timeout=self.timeout,
            )
            return r.json()
        except Exception as e:
            raise GovernanceError(f"Quarantine failed: {e}")

    def reinstate(self, reason=""):
        """
        Reinstate the agent. Tool calls resume immediately.
        """
        self._ensure_credential()
        agent_id = self._agent_id or self._credential.get("agent_id", "")
        if not agent_id:
            raise GovernanceError("No agent_id available. Fetch credential first.")
        try:
            r = self._session.post(
                f"{self.gateway_url}/agent/{agent_id}/reinstate",
                json={"reason": reason},
                timeout=self.timeout,
            )
            return r.json()
        except Exception as e:
            raise GovernanceError(f"Reinstate failed: {e}")

    def kill(self, reason=""):
        """
        Kill switch is only available through the PhronEdge console.
        Visit phronedge.com/brain to terminate an agent.
        """
        raise GovernanceError(
            "Kill switch is not available in the SDK. "
            "Use the PhronEdge console at phronedge.com/brain to terminate an agent."
        )
