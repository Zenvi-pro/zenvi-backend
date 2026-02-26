"""
Server-side research tools wrapping the Perplexity Sonar client.
No Qt dependency — runs entirely on the backend.
"""

from logger import log


def _get_perplexity_key() -> str:
    from config import get_settings
    return (get_settings().perplexity_api_key or "").strip()


def test_perplexity_api_key() -> str:
    """Check if the Perplexity API key is configured."""
    key = _get_perplexity_key()
    if not key:
        return "Perplexity API key is NOT configured. Set PERPLEXITY_API_KEY in the backend .env file."
    if len(key) < 20:
        return f"Perplexity API key looks invalid (too short: {len(key)} chars). Check PERPLEXITY_API_KEY."
    return "Perplexity is configured (model: sonar-pro). Ready to research!"


def research_web(
    query: str,
    max_images: int = 3,
    search_domain_filter: str = "",
    search_recency_filter: str = "",
    timeout_seconds: float = 120.0,
) -> str:
    """
    Search the web using Perplexity Sonar and return formatted results.
    Images are downloaded to a temp directory on the server.
    """
    from core.providers.perplexity_client import research_and_download_images, PerplexityError
    import os, tempfile, uuid

    query = (query or "").strip()
    if not query:
        return "Error: query is required."

    api_key = _get_perplexity_key()
    if not api_key:
        return "Perplexity is not configured. Set PERPLEXITY_API_KEY in the backend .env file."

    max_imgs = max(0, min(10, int(max_images)))
    domain_filter = [d.strip() for d in (search_domain_filter or "").split(",") if d.strip()]

    dest_dir = os.path.join(tempfile.gettempdir(), f"zenvi_research_{uuid.uuid4().hex[:8]}")
    os.makedirs(dest_dir, exist_ok=True)

    try:
        result = research_and_download_images(
            api_key=api_key,
            query=query,
            max_images=max_imgs,
            dest_dir=dest_dir,
            model="sonar-pro",
            search_domain_filter=domain_filter,
            search_recency_filter=(search_recency_filter or "").strip(),
            timeout_seconds=float(timeout_seconds),
        )
    except PerplexityError as exc:
        log.error("Research failed: %s", exc)
        return f"Research failed: {exc}"
    except Exception as exc:
        log.error("Research failed: %s", exc, exc_info=True)
        return f"Error: {exc}"

    # Format output
    parts = []
    summary = result.get("summary", "")
    if summary:
        parts.append(summary)

    downloaded = result.get("downloaded_images", [])
    if downloaded:
        parts.append(f"\n**IMAGES FOUND:** {len(downloaded)} image(s) downloaded")
        for i, img in enumerate(downloaded, 1):
            desc = img.get("description", "Image")
            path = img.get("path", "")
            parts.append(f"{i}. {desc} → {path}")

    failed = result.get("failed_images", [])
    if failed:
        parts.append(f"\n**Note:** {len(failed)} image(s) could not be downloaded")

    citations = result.get("citations", [])
    if citations:
        parts.append("\n**SOURCES:**")
        for i, url in enumerate(citations, 1):
            parts.append(f"{i}. {url}")

    related = result.get("related_questions", [])
    if related:
        parts.append("\n**RELATED QUESTIONS:**")
        for q in related:
            parts.append(f"- {q}")

    return "\n".join(parts) if parts else "Research completed but no results found."


def research_for_content_planning(
    topic: str,
    content_type: str = "video",
    aspects: str = "",
    timeout_seconds: float = 90.0,
) -> str:
    """
    Research a topic for content-planning (colours, mood, transitions, etc.).
    """
    from core.providers.perplexity_client import perplexity_search, PerplexityError

    topic = (topic or "").strip()
    if not topic:
        return "Error: topic is required."

    api_key = _get_perplexity_key()
    if not api_key:
        return "Perplexity is not configured. Set PERPLEXITY_API_KEY in the backend .env file."

    # Build enriched query based on aspects
    query_parts = [topic]
    if aspects:
        aspect_list = [a.strip() for a in aspects.split(",") if a.strip()]
        if "visuals" in aspect_list:
            query_parts.append("visual style cinematography")
        if "colors" in aspect_list:
            query_parts.append("color palette grading")
        if "sounds" in aspect_list:
            query_parts.append("sound design music score")
        if "transitions" in aspect_list:
            query_parts.append("editing transitions effects")
        if "mood" in aspect_list:
            query_parts.append("mood atmosphere pacing")
    query = " ".join(query_parts)

    try:
        result = perplexity_search(
            api_key=api_key,
            query=query,
            model="sonar-pro",
            return_images=True,
            return_related_questions=True,
            timeout_seconds=float(timeout_seconds),
        )
    except PerplexityError as exc:
        log.error("Content planning failed: %s", exc)
        return f"Content planning failed: {exc}"
    except Exception as exc:
        log.error("Content planning failed: %s", exc, exc_info=True)
        return f"Error: {exc}"

    parts = []
    summary = result.get("content", "")
    if summary:
        parts.append(f"**{topic.upper()} — CONTENT PLANNING**\n")
        parts.append(summary)

    citations = result.get("citations", [])
    if citations:
        parts.append("\n**SOURCES:**")
        for i, url in enumerate(citations, 1):
            parts.append(f"{i}. {url}")

    parts.append("\n**NEXT STEPS:**")
    if "music" in (aspects or "") or "sounds" in (aspects or ""):
        parts.append("- Use the Music Agent to generate background music matching this style")
    if "transitions" in (aspects or ""):
        parts.append("- Use the Transitions Agent to apply recommended transition effects")
    if "colors" in (aspects or "") or "visuals" in (aspects or ""):
        parts.append("- Apply color grading adjustments using the Video Agent")

    related = result.get("related_questions", [])
    if related:
        parts.append("\n**EXPLORE FURTHER:**")
        for q in related[:3]:
            parts.append(f"- {q}")

    return "\n".join(parts) if parts else "Content planning completed but no recommendations generated."


# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------

def get_research_tools_for_langchain():
    from langchain_core.tools import tool

    @tool
    def test_perplexity_api_key_tool() -> str:
        """Check if Perplexity is configured and the API key is set."""
        return test_perplexity_api_key()

    @tool
    def research_web_tool(
        query: str = "",
        max_images: int = 3,
        search_domain_filter: str = "",
        search_recency_filter: str = "",
        timeout_seconds: str = "120",
    ) -> str:
        """
        Search the web using Perplexity and return AI-powered answers with citations and images.

        - query: Search query (required)
        - max_images: Number of images to download (0-10, default 3)
        - search_domain_filter: Comma-separated domains (e.g. "wikipedia.org,imdb.com")
        - search_recency_filter: "month", "week", "day", or empty
        """
        return research_web(
            query=query,
            max_images=int(max_images) if str(max_images).strip() else 3,
            search_domain_filter=search_domain_filter,
            search_recency_filter=search_recency_filter,
            timeout_seconds=float(timeout_seconds) if str(timeout_seconds).strip() else 120.0,
        )

    @tool
    def research_for_content_planning_tool(
        topic: str = "",
        content_type: str = "video",
        aspects: str = "",
        timeout_seconds: str = "90",
    ) -> str:
        """
        Research a topic and get actionable content suggestions for video editing.

        - topic: Topic to research (required, e.g. "Stranger Things", "cyberpunk aesthetic")
        - content_type: "video", "music", or "aesthetic"
        - aspects: Comma-separated (e.g. "visuals,colors,sounds,transitions,mood")
        """
        return research_for_content_planning(
            topic=topic,
            content_type=content_type,
            aspects=aspects,
            timeout_seconds=float(timeout_seconds) if str(timeout_seconds).strip() else 90.0,
        )

    return [test_perplexity_api_key_tool, research_web_tool, research_for_content_planning_tool]
