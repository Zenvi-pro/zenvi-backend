"""
Video generation tools — text-to-video, V2V insert, transition generation.

These are frontend-delegated because they need to add the generated file to the
project and timeline (Qt operations). The actual video generation call goes
through the backend's generation API.
"""

from langchain_core.tools import tool


_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


@tool
def generate_video_and_add_to_timeline_tool(
    prompt: str,
    duration_seconds: str = "",
    position_seconds: str = "",
    track: str = "",
) -> str:
    """Generate a brand-new standalone video from a text prompt using AI (Runware/Vidu) and add it to the timeline. ONLY use this tool when the user wants to create an entirely new video from scratch (no existing clip involved). Do NOT use this tool when the user says 'insert into', 'add to', or 'modify' a selected clip — use insert_vidu_v2v_clip_into_selected_clip_tool for that instead. Argument: prompt (required, describe the video). Optional: duration_seconds (default from settings, e.g. 4); position_seconds (empty for playhead); track (empty for selected or first track)."""
    return _NO_FRONTEND


@tool
def insert_vidu_v2v_clip_into_selected_clip_tool(query: str, fade_ms: str = "400") -> str:
    """Insert an AI-generated 4s clip into the currently selected timeline clip using Vidu V2V. This is the ONLY tool to use when the user says 'insert', 'add into', 'modify', or 'change' the selected clip. It finds the best insertion point, generates a video-to-video clip, bakes it into the original with crossfades, and imports the combined clip into the project files panel. The original clip on the timeline is left unchanged. Do NOT also call generate_video_and_add_to_timeline_tool — this tool handles everything and only produces ONE imported file.

    Args:
        query: what to add/change (single simple action)
        fade_ms: crossfade duration in milliseconds (<500). Default 400.
    """
    return _NO_FRONTEND


@tool
def generate_transition_clip_tool(clip_a_id: str, clip_b_id: str, prompt_hint: str = "") -> str:
    """Generate a short transition clip between two clips and insert it between them. Arguments: clip_a_id, clip_b_id, prompt_hint (optional)."""
    return _NO_FRONTEND


def get_video_gen_tools():
    """Return all video generation LangChain tools."""
    return [
        generate_video_and_add_to_timeline_tool,
        insert_vidu_v2v_clip_into_selected_clip_tool,
        generate_transition_clip_tool,
    ]
