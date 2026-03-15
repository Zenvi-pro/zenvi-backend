"""
Server-side search tools for the AI agent.
Wraps TwelveLabs and scene-description search.
"""

from logger import log

# Maps ordinal words to 1-based occurrence indices
_ORDINAL_MAP = {
    "first": 1, "1st": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
    "fifth": 5, "5th": 5,
}


def _detect_ordinal(query: str) -> int:
    """Return a 1-based occurrence index if the query contains an ordinal word, else 0."""
    words = query.lower().split()
    for word in words:
        if word in _ORDINAL_MAP:
            return _ORDINAL_MAP[word]
    return 0


def _fmt_timestamp(seconds: float) -> str:
    """Format seconds as M:SS.s (e.g. 1:23.4s)."""
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m}:{s:04.1f}"


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

        # Detect ordinal in query so we can resolve "first/second/etc." directly
        requested_nth = _detect_ordinal(query)

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
                    f"  • {filename} — timestamp {_fmt_timestamp((r['start'] + r['end']) / 2)} "
                    f"(segment {r['start']:.1f}s–{r['end']:.1f}s, score: {r['score']:.2f})"
                )
            else:
                # Multiple occurrences — sort chronologically
                hits_sorted = sorted(hits, key=lambda x: x["start"])

                if requested_nth > 0:
                    # User specified an ordinal — pick that occurrence directly
                    idx = min(requested_nth - 1, len(hits_sorted) - 1)
                    r = hits_sorted[idx]
                    ordinal_words = {v: k for k, v in _ORDINAL_MAP.items() if len(k) <= 4}
                    label = ordinal_words.get(requested_nth, f"#{requested_nth}")
                    lines.append(
                        f"  • {filename} — {label} occurrence at timestamp {_fmt_timestamp((r['start'] + r['end']) / 2)} "
                        f"(segment {r['start']:.1f}s–{r['end']:.1f}s, score: {r['score']:.2f})"
                    )
                else:
                    # No ordinal specified — list all and ask
                    lines.append(f"  • {filename} — {len(hits_sorted)} occurrences:")
                    for i, r in enumerate(hits_sorted, 1):
                        lines.append(
                            f"      {i}. timestamp {_fmt_timestamp((r['start'] + r['end']) / 2)} "
                            f"(segment {r['start']:.1f}s–{r['end']:.1f}s, score: {r['score']:.2f})"
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
