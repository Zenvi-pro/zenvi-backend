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
        # search_index returns a dict with "error" key on failure
        if isinstance(results, dict) and "error" in results:
            return f"Error: {results['error']}"
        if not results:
            return (
                f"No results found for '{query}'. "
                "Try a more specific description (e.g. add context like colour, action, or object)."
            )

        # Group by filename so we can detect repeated occurrences in the same video
        from collections import defaultdict
        grouped: dict = defaultdict(list)
        for r in results:
            key = r.get("filename") or r.get("video_id") or "unknown"
            grouped[key].append(r)

        lines = [f"Found {len(results)} match(es) across {len(grouped)} video(s):"]
        for filename, hits in grouped.items():
            if len(hits) == 1:
                r = hits[0]
                lines.append(
                    f"  • {filename} — {r['start']:.1f}s–{r['end']:.1f}s (score: {r['score']:.2f})"
                )
            else:
                # Multiple occurrences of the same event in one video
                lines.append(f"  • {filename} — {len(hits)} occurrences:")
                for i, r in enumerate(hits, 1):
                    lines.append(
                        f"      {i}. {r['start']:.1f}s–{r['end']:.1f}s (score: {r['score']:.2f})"
                    )
                lines.append(
                    f"      Multiple matches in '{filename}' — ask the user which occurrence they mean "
                    f"(e.g. 'the 1st time', 'the 2nd time', etc.)."
                )

        return "\n".join(lines)
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
