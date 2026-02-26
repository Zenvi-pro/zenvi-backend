"""
Director Analysis Tools — frontend-delegated stubs.

All 8 analysis tools access the Qt project state (Clip, Track, File objects)
so they MUST run on the frontend. The backend registers them as LangChain tools
that return the _NO_FRONTEND sentinel; the WebSocket agent runner then delegates
the actual invocation to the desktop client.

Ported from core/src/classes/ai_directors/director_tools.py.
"""

from __future__ import annotations

from typing import List

from langchain_core.tools import StructuredTool

_NO_FRONTEND = (
    "This tool reads project state and must be executed by the "
    "desktop front-end.  The backend returns this sentinel so the WebSocket "
    "agent runner knows to delegate."
)

# ---------------------------------------------------------------------------
# Tool name sets (for FRONTEND_TOOL_NAMES registration)
# ---------------------------------------------------------------------------

DIRECTOR_FRONTEND_TOOL_NAMES = {
    "analyze_timeline_structure_tool",
    "analyze_pacing_tool",
    "analyze_audio_levels_tool",
    "analyze_transitions_tool",
    "analyze_clip_content_tool",
    "analyze_music_sync_tool",
    "get_project_metadata_tool",
    "analyze_clip_visual_content_tool",
}


# ---------------------------------------------------------------------------
# Stub implementations — return _NO_FRONTEND so agent_runner delegates
# ---------------------------------------------------------------------------


def analyze_timeline_structure() -> str:
    """Get overview of timeline structure: tracks, clips, transitions, effects."""
    return _NO_FRONTEND


def analyze_pacing() -> str:
    """Analyze video pacing: cut frequency, scene durations, average clip length."""
    return _NO_FRONTEND


def analyze_audio_levels() -> str:
    """Analyze audio levels: volume, mixing, audio track information."""
    return _NO_FRONTEND


def analyze_transitions() -> str:
    """Analyze transitions: types used, frequency, timing."""
    return _NO_FRONTEND


def analyze_clip_content() -> str:
    """Analyze visual content of clips using AI metadata and scene descriptions."""
    return _NO_FRONTEND


def analyze_music_sync() -> str:
    """Analyze music beat alignment with video cuts."""
    return _NO_FRONTEND


def get_project_metadata() -> str:
    """Get project metadata: duration, resolution, fps, format."""
    return _NO_FRONTEND


def analyze_clip_visual_content(clip_id: str = "") -> str:
    """Analyze visual content using AI vision: composition, objects, scenes, mood, quality issues."""
    return _NO_FRONTEND


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_director_analysis_tools_for_langchain() -> List[StructuredTool]:
    """Return all director analysis tools wrapped for LangChain."""
    return [
        StructuredTool.from_function(
            func=analyze_timeline_structure,
            name="analyze_timeline_structure_tool",
            description="Get overview of timeline structure: tracks, clips, transitions, effects.",
        ),
        StructuredTool.from_function(
            func=analyze_pacing,
            name="analyze_pacing_tool",
            description="Analyze video pacing: cut frequency, scene durations, average clip length.",
        ),
        StructuredTool.from_function(
            func=analyze_audio_levels,
            name="analyze_audio_levels_tool",
            description="Analyze audio levels: volume, mixing, audio track information.",
        ),
        StructuredTool.from_function(
            func=analyze_transitions,
            name="analyze_transitions_tool",
            description="Analyze transitions: types used, frequency, timing.",
        ),
        StructuredTool.from_function(
            func=analyze_clip_content,
            name="analyze_clip_content_tool",
            description="Analyze visual content of clips using AI metadata and scene descriptions.",
        ),
        StructuredTool.from_function(
            func=analyze_music_sync,
            name="analyze_music_sync_tool",
            description="Analyze music beat alignment with video cuts.",
        ),
        StructuredTool.from_function(
            func=get_project_metadata,
            name="get_project_metadata_tool",
            description="Get project metadata: duration, resolution, fps, format.",
        ),
        StructuredTool.from_function(
            func=analyze_clip_visual_content,
            name="analyze_clip_visual_content_tool",
            description="Analyze visual content using AI vision: composition, objects, scenes, mood, quality issues.",
        ),
    ]
