"""
Project information and lifecycle tools.

All of these tools require the running Qt application and are therefore
delegated to the frontend via the agent runner's tool_executor callback.
The function bodies below are fallback stubs that execute only when no
frontend is connected.
"""

from langchain_core.tools import tool


_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


@tool
def get_project_info_tool() -> str:
    """Get current project info: profile, fps, duration, scale. No arguments."""
    return _NO_FRONTEND


@tool
def list_files_tool() -> str:
    """List all files in the project. No arguments."""
    return _NO_FRONTEND


@tool
def list_clips_tool(layer: str = "") -> str:
    """List clips in the project. Optional: layer (number) to filter by layer."""
    return _NO_FRONTEND


@tool
def list_layers_tool() -> str:
    """List all layers (tracks) in the project. No arguments."""
    return _NO_FRONTEND


@tool
def list_markers_tool() -> str:
    """List all markers in the project. No arguments."""
    return _NO_FRONTEND


@tool
def new_project_tool() -> str:
    """Create a new empty project."""
    return _NO_FRONTEND


@tool
def save_project_tool(file_path: str) -> str:
    """Save the project to the given file path. Example: /home/user/my.zvn"""
    return _NO_FRONTEND


@tool
def open_project_tool(file_path: str) -> str:
    """Open a project from the given file path."""
    return _NO_FRONTEND


def get_project_tools():
    """Return all project-related LangChain tools."""
    return [
        get_project_info_tool,
        list_files_tool,
        list_clips_tool,
        list_layers_tool,
        list_markers_tool,
        new_project_tool,
        save_project_tool,
        open_project_tool,
    ]
