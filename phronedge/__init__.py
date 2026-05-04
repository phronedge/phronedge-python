"""
PhronEdge  - Runtime AI Governance
=========================================

    pip install phronedge

    from phronedge import PhronEdge

    pe = PhronEdge()

    @pe.govern("lookup_claim")
    def lookup_claim(claim_id: str) -> str:
        return db.query(claim_id)

Every call goes through 7 constitutional checkpoints.
Works with any framework. One API key. Zero config.
"""

from phronedge.client import PhronEdge, GovernanceError, ToolBlocked, AgentTerminated

__version__ = "2.5.0"
__all__ = ["PhronEdge", "GovernanceError", "ToolBlocked", "AgentTerminated"]
