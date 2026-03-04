"""
Search tools for finding moments within timeline clips.

These tools combine server-side search (TwelveLabs) with frontend state
(selected clip, source file metadata). They are frontend-delegated because
they need the Qt app to read clip/file data, but the actual search queries
hit the backend indexing and scene_description_search services.
"""

from langchain_core.tools import tool


_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


@tool
def search_selected_clip_scenes_tool(query: str, top_k: str = "5", use_openai_rerank: str = "true") -> str:
    """Search within the currently selected timeline clip's time window. Uses TwelveLabs when indexed; otherwise falls back to local scene_descriptions (optionally OpenAI rerank).

    Args:
        query: natural language query
        top_k: number of results (default 5)
        use_openai_rerank: 'true'/'false' (default true)
    """
    return _NO_FRONTEND


@tool
def slice_selected_clip_at_best_match_tool(query: str, occurrence: str = "0") -> str:
    """Slice the selected timeline clip at the best match inside its time window (TwelveLabs preferred, else scene_descriptions).

    Args:
        query: natural language description of the moment to find (strip any ordinal words like 'first', 'second' from here)
        occurrence: which occurrence to use when multiple matches exist.
            '0' = highest-scoring match (default).
            '1' = first chronological match, '2' = second, etc.
            Always pass this when the user says 'first time', 'second time', etc.
    """
    return _NO_FRONTEND


def get_search_clip_tools():
    """Return all clip search LangChain tools."""
    return [
        search_selected_clip_scenes_tool,
        slice_selected_clip_at_best_match_tool,
    ]
