"""
Export tools.

Frontend-delegated — require the running Qt export dialog / headless exporter.
"""

from langchain_core.tools import tool


_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


@tool
def export_video_tool() -> str:
    """Open the export video dialog. Use when the user wants to see or use the full export dialog."""
    return _NO_FRONTEND


@tool
def get_export_settings_tool() -> str:
    """Get current/default export settings (resolution, fps, codecs, format, path, frame range). Use when the user asks what their export settings are."""
    return _NO_FRONTEND


@tool
def set_export_setting_tool(key: str, value: str) -> str:
    """Set a single export setting. Keys: width, height, fps_num, fps_den, video_codec, audio_codec, output_path, start_frame, end_frame, vformat. Value is a string (e.g. 1920, 30, libx264)."""
    return _NO_FRONTEND


@tool
def export_video_now_tool(output_path: str = "") -> str:
    """Export the video with current/default settings without opening the dialog. Use when the user says 'export the video' or 'export with current settings'. Optional output_path; if empty, uses default path."""
    return _NO_FRONTEND


def get_export_tools():
    """Return all export LangChain tools."""
    return [
        export_video_tool,
        get_export_settings_tool,
        set_export_setting_tool,
        export_video_now_tool,
    ]
