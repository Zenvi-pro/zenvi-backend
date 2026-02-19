"""
Clip splitting, slicing, and adding-to-timeline tools.

Frontend-delegated — require project query classes and the live timeline.
"""

from langchain_core.tools import tool


_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


@tool
def get_file_info_tool(file_id: str) -> str:
    """Get file metadata: fps, video_length, path. Use before split_file_add_clip to validate frame range. Argument: file_id (string)."""
    return _NO_FRONTEND


@tool
def split_file_add_clip_tool(file_id: str, start_frame: int, end_frame: int, name: str = "") -> str:
    """Create a new clip from a file by frame range and add it to the project (no dialog). Use when the user wants to split a file or create a clip from frames. Arguments: file_id (string), start_frame (int, 1-based), end_frame (int, 1-based), name (optional string)."""
    return _NO_FRONTEND


@tool
def add_clip_to_timeline_tool(file_id: str = "", position_seconds: str = "", track: str = "") -> str:
    """Add the clip just created by split_file_add_clip to the timeline at the playhead. Call with no arguments when the user says yes to adding the clip to the timeline (the app remembers which clip was just created). Optional: file_id only if adding a different specific file; position_seconds (empty for playhead); track (empty for selected or first track)."""
    return _NO_FRONTEND


@tool
def slice_clip_at_playhead_tool() -> str:
    """Slice (split) the clip(s) and transition(s) at the current playhead position on the timeline, keeping both sides. Fails if no clip is under the playhead."""
    return _NO_FRONTEND


def get_clip_tools():
    """Return all clip-related LangChain tools."""
    return [
        get_file_info_tool,
        split_file_add_clip_tool,
        add_clip_to_timeline_tool,
        slice_clip_at_playhead_tool,
    ]
