"""
Transitions tools — frontend-delegated stubs.

These tools manipulate the live OpenShot project (Qt app) and must run on the
frontend. The backend defines the tool schemas so the LLM agent can call them;
actual execution is forwarded to the frontend via WebSocket.
"""

from langchain_core.tools import tool

_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


@tool
def list_transitions_tool(category: str = "all") -> str:
    """List all available transitions. category: "all", "common", or "extra". Returns JSON list of transitions."""
    return _NO_FRONTEND


@tool
def search_transitions_tool(query: str) -> str:
    """Search for transitions by name. query: search term (e.g. "fade", "wipe", "circle"). Returns matching transitions."""
    return _NO_FRONTEND


@tool
def add_transition_between_clips_tool(clip1_id: str, clip2_id: str, transition_name: str, duration: str = "1.0") -> str:
    """Add a transition between two clips. Use list_clips_tool first to get clip IDs, then search_transitions_tool to find a transition name. duration in seconds (default 1.0)."""
    return _NO_FRONTEND


@tool
def add_transition_to_clip_tool(clip_id: str, transition_name: str, position: str = "start", duration: str = "1.0") -> str:
    """Add a transition (fade in/out) to a single clip. position: "start" or "end". duration in seconds (default 1.0)."""
    return _NO_FRONTEND


def get_transitions_tools():
    """Return all transition tool objects."""
    return [
        list_transitions_tool,
        search_transitions_tool,
        add_transition_between_clips_tool,
        add_transition_to_clip_tool,
    ]
