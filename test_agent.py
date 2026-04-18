from phronedge import PhronEdge
pe = PhronEdge(agent_id="agt-adverse-v1")

@pe.govern("adverse_events", action="read", jurisdiction="DE")
def lookup_adverse(event_id: str) -> dict:
    """Look up an adverse event."""
    return {"id": event_id}

def send_email(to: str, body: str) -> str:
    """Send an email — intentionally ungoverned."""
    return "sent"
