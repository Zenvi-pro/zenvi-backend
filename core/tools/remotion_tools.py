"""
LangChain tool wrappers for the Remotion rendering service.

Rendering paths:
1. render_remotion_from_repo_tool         — full service (port 4500), async job queue.
2. render_remotion_product_launch_tool    — product-launch service (port 3100), renders
                                            and uploads the video to Supabase bucket
                                            "product_demo", returns the public URL.
3. fetch_remotion_video_from_supabase_tool — FRONTEND-DELEGATED: downloads the Supabase
                                            URL and imports the file into project files.
4. check_remotion_health_tool             — health check for both services.
"""

from __future__ import annotations

from logger import log

_NO_FRONTEND = "Error: This tool requires the frontend to be connected via WebSocket."


def _full_client():
    from core.providers.remotion_client import RemotionClient
    from config import get_settings
    url = get_settings().remotion_url
    return RemotionClient(base_url=url)


def _product_launch_url() -> str:
    from config import get_settings
    return get_settings().remotion_product_launch_url


# ---------------------------------------------------------------------------
# Standalone functions
# ---------------------------------------------------------------------------


def check_remotion_health() -> str:
    """Return a status summary for both Remotion services."""
    from core.providers.remotion_client import check_remotion_service

    full_ok = _full_client().health_check()
    pl_ok = check_remotion_service(_product_launch_url())

    lines = [
        f"Full Remotion service: {'✅ running' if full_ok else '❌ not reachable'}",
        f"Product-launch service: {'✅ running' if pl_ok else '❌ not reachable'}",
    ]
    if not full_ok and not pl_ok:
        lines.append("\nNeither Remotion service is reachable. Please contact support or try again later.")
    return "\n".join(lines)


def render_remotion_from_repo(
    repo_url: str,
    style: str = "modern",
    duration: int = 30,
    output_path: str | None = None,
) -> str:
    """Render a video from a GitHub repo using the full Remotion service (port 4500)."""
    from core.providers.remotion_client import RemotionError
    from core.providers.github_client import get_repo_data_from_url, parse_github_url, GitHubError
    from config import get_settings

    client = _full_client()
    if not client.health_check():
        return "❌ Remotion rendering service is currently unavailable. Please try again later or contact support."

    try:
        token = get_settings().github_token or ""
        owner, repo = parse_github_url(repo_url)
        if not owner or not repo:
            return f"Error: Could not parse GitHub URL: {repo_url}"

        log.info("Fetching GitHub data for %s/%s for Remotion render", owner, repo)
        repo_data = get_repo_data_from_url(repo_url, token=token)

        log.info("Submitting Remotion render job for %s/%s (style=%s, duration=%ds)", owner, repo, style, duration)
        video_path = client.render_and_wait(
            client.render_from_repo,
            repo_url,
            repo_data,
            style=style,
            duration=duration,
            output_path=output_path,
        )
        return (
            f"✅ Remotion render complete for '{owner}/{repo}'.\n"
            f"Video saved to: {video_path}\n"
            "Use add_clip_to_timeline_tool to add this video to the timeline."
        )

    except GitHubError as e:
        return f"Error fetching GitHub data: {e}"
    except RemotionError as e:
        return f"Error during Remotion render: {e}"
    except Exception as e:
        log.error("Remotion render_from_repo failed: %s", e, exc_info=True)
        return f"Unexpected error: {e}"


def render_remotion_product_launch(
    repo_url: str,
    style: str = "modern",
    duration: int = 30,
) -> str:
    """
    Render a product-launch video via the Remotion product-launch service.

    The service renders the video, uploads it to the Supabase 'product_demo'
    bucket, and returns the public URL. Returns a result string containing
    the supabase_url so the agent can pass it to
    fetch_remotion_video_from_supabase_tool.
    """
    from core.providers.remotion_client import check_remotion_service
    from core.providers.github_client import get_repo_data_from_url, parse_github_url, GitHubError
    from config import get_settings
    import requests

    pl_url = _product_launch_url()
    if not check_remotion_service(pl_url):
        return "❌ Remotion product-launch service is currently unavailable. Please try again later or contact support."

    try:
        token = get_settings().github_token or ""
        owner, repo = parse_github_url(repo_url)
        if not owner or not repo:
            return f"Error: Could not parse GitHub URL: {repo_url}"

        log.info("Fetching GitHub data for %s/%s for product-launch render", owner, repo)
        repo_data = get_repo_data_from_url(repo_url, token=token)

        log.info("Rendering product-launch video (style=%s, duration=%ds)", style, duration)
        payload = {"repo_data": repo_data, "style": style, "duration": duration}
        resp = requests.post(f"{pl_url}/api/render", json=payload, timeout=300)

        if resp.status_code == 413:
            return f"❌ Render failed: {resp.json().get('error', 'File too large for upload (50 MB cap).')}"
        if resp.status_code != 200:
            return f"❌ Product-launch render failed: HTTP {resp.status_code} — {resp.text[:200]}"

        data = resp.json()
        if data.get("status") != "completed":
            return f"❌ Product-launch render failed: {data.get('error', 'unknown error')}"

        supabase_url = data.get("supabase_url", "")
        supabase_path = data.get("supabase_path", "")

        if not supabase_url:
            return "❌ Render succeeded but no Supabase URL was returned."

        log.info("Product-launch video uploaded to Supabase: %s", supabase_url)
        return (
            f"✅ Product-launch video rendered and uploaded for '{owner}/{repo}'.\n"
            f"Supabase URL: {supabase_url}\n"
            f"Supabase path: {supabase_path}\n"
            f"Now call fetch_remotion_video_from_supabase_tool with "
            f"supabase_url='{supabase_url}' and supabase_path='{supabase_path}' "
            f"to download it, import it into the project files, and delete it from Supabase."
        )

    except GitHubError as e:
        return f"Error fetching GitHub data: {e}"
    except Exception as e:
        log.error("Remotion product-launch render failed: %s", e, exc_info=True)
        return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------


def get_remotion_tools_for_langchain():
    from langchain_core.tools import tool

    @tool
    def check_remotion_health_tool() -> str:
        """Check whether the Remotion rendering services are running and reachable."""
        return check_remotion_health()

    @tool
    def render_remotion_from_repo_tool(
        repo_url: str,
        style: str = "modern",
        duration: int = 30,
    ) -> str:
        """
        Render a video for a GitHub repository using the full Remotion service.
        Fetches repo data, submits an async render job, polls until done, and saves locally.

        Args:
            repo_url: GitHub repository URL (e.g. github.com/owner/repo)
            style: Visual style — "modern", "minimal", "bold" (default: "modern")
            duration: Video duration in seconds (default: 30)
        """
        return render_remotion_from_repo(repo_url, style=style, duration=duration)

    @tool
    def render_remotion_product_launch_tool(
        repo_url: str,
        style: str = "modern",
        duration: int = 30,
    ) -> str:
        """
        Render a product-launch promotional video for a GitHub repository.
        Fetches repo data, renders via the product-launch Remotion service, and uploads
        the result to Supabase storage (bucket: product_demo, 50 MB cap).
        Returns the Supabase public URL — then call fetch_remotion_video_from_supabase_tool
        with that URL to import the video into the project.

        Args:
            repo_url: GitHub repository URL (e.g. github.com/owner/repo)
            style: Visual style — "modern", "minimal", "bold" (default: "modern")
            duration: Video duration in seconds (default: 30)
        """
        return render_remotion_product_launch(repo_url, style=style, duration=duration)

    @tool
    def fetch_remotion_video_from_supabase_tool(supabase_url: str, supabase_path: str = "") -> str:
        """
        FRONTEND TOOL — Download the rendered Remotion video from its Supabase public URL,
        import it into the project files panel, then delete the file from Supabase storage.
        Call this immediately after render_remotion_product_launch_tool succeeds.

        Args:
            supabase_url: The public Supabase URL returned by render_remotion_product_launch_tool
            supabase_path: The Supabase storage path returned by render_remotion_product_launch_tool (used for post-import cleanup)
        """
        return _NO_FRONTEND

    return [
        check_remotion_health_tool,
        render_remotion_from_repo_tool,
        render_remotion_product_launch_tool,
        fetch_remotion_video_from_supabase_tool,
    ]
