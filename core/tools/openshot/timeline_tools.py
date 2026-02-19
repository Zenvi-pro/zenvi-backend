"""
Timeline/view manipulation tools.

Frontend-delegated — require the running Qt timeline widget.
"""

from langchain_core.tools import tool


_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


@tool
def add_track_tool() -> str:
    """Add a new track (layer) below the selected track."""
    return _NO_FRONTEND


@tool
def add_marker_tool() -> str:
    """Add a marker at the current playhead position."""
    return _NO_FRONTEND


@tool
def remove_clip_tool() -> str:
    """Remove the currently selected clip(s) from the timeline."""
    return _NO_FRONTEND


@tool
def zoom_in_tool() -> str:
    """Zoom in the timeline."""
    return _NO_FRONTEND


@tool
def zoom_out_tool() -> str:
    """Zoom out the timeline."""
    return _NO_FRONTEND


@tool
def center_on_playhead_tool() -> str:
    """Center the timeline view on the playhead."""
    return _NO_FRONTEND


@tool
def import_files_tool() -> str:
    """Open the import files dialog."""
    return _NO_FRONTEND


def get_timeline_tools():
    """Return all timeline/view LangChain tools."""
    return [
        add_track_tool,
        add_marker_tool,
        remove_clip_tool,
        zoom_in_tool,
        zoom_out_tool,
        center_on_playhead_tool,
        import_files_tool,
    ]
