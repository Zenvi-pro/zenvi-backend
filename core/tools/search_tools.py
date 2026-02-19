"""
Server-side search tools for the AI agent.
Wraps TwelveLabs and scene-description search.
"""

from logger import log


def search_clips(query: str, top_k: int = 5) -> str:
    """Search for clips matching a query using TwelveLabs or local scene descriptions."""
    try:
        from core.indexing.twelvelabs import search_index
        results = search_index(query, top_k=top_k)
        if results:
            return f"Found {len(results)} matches: " + "; ".join(
                f"{r.get('filename', 'unknown')} (score: {r.get('score', 0):.2f})" for r in results
            )
    except Exception as e:
        log.debug("TwelveLabs search not available: %s", e)
    return f"No results found for '{query}'. TwelveLabs indexing may not be configured."


def get_search_tools_for_langchain():
    from langchain_core.tools import tool

    @tool
    def search_clips_tool(query: str, top_k: int = 5) -> str:
        """Search for clips matching a description using TwelveLabs or scene descriptions."""
        return search_clips(query, top_k)

    return [search_clips_tool]
