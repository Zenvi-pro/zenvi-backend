"""
Playback and history tools.

Frontend-delegated — require the running Qt preview player.
"""

from langchain_core.tools import tool


_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


@tool
def play_tool() -> str:
    """Start or toggle playback."""
    return _NO_FRONTEND


@tool
def go_to_start_tool() -> str:
    """Seek to the start of the timeline."""
    return _NO_FRONTEND


@tool
def go_to_end_tool() -> str:
    """Seek to the end of the timeline."""
    return _NO_FRONTEND


@tool
def undo_tool() -> str:
    """Undo the last action."""
    return _NO_FRONTEND


@tool
def redo_tool() -> str:
    """Redo the last undone action."""
    return _NO_FRONTEND


def get_playback_tools():
    """Return all playback/history LangChain tools."""
    return [
        play_tool,
        go_to_start_tool,
        go_to_end_tool,
        undo_tool,
        redo_tool,
    ]
