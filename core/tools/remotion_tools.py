"""
LangChain tool wrappers for the Remotion rendering service.

Two rendering paths:
1. render_remotion_from_repo_tool  — full service (port 4500), renders from a GitHub repo URL.
2. render_remotion_product_launch_tool — simpler service (port 3100), product-launch videos.
3. check_remotion_health_tool — check which Remotion services are reachable.
"""

from __future__ import annotations

import json
from logger import log


def _full_client():
    from core.providers.remotion_client import RemotionClient
    from config import get_settings
    url = get_settings().remotion_url
    return RemotionClient(base_url=url)


def _product_launch_url() -> str:
    from config import get_settings
    return get_settings().remotion_product_launch_url


# ---------------------------------------------------------------------------
# Standalone functions (called by LangChain tools below)
# ---------------------------------------------------------------------------


def check_remotion_health() -> str:
    """Return a status summary for both Remotion services."""
    from core.providers.remotion_client import check_remotion_service

    full_ok = _full_client().health_check()
    pl_ok = check_remotion_service(_product_launch_url())

    lines = [
        f"Full Remotion service (port 4500): {'✅ running' if full_ok else '❌ not reachable'}",
        f"Product-launch service (port 3100): {'✅ running' if pl_ok else '❌ not reachable'}",
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
    output_path: str | None = None,
) -> str:
    """Render a product-launch video using the simpler Remotion service (port 3100)."""
    from core.providers.remotion_client import render_product_launch_video, check_remotion_service, RemotionError
    from core.providers.github_client import get_repo_data_from_url, parse_github_url, GitHubError
    from config import get_settings

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
        video_path = render_product_launch_video(
            repo_data=repo_data,
            style=style,
            duration=duration,
            base_url=pl_url,
            output_path=output_path,
        )

        if video_path:
            return (
                f"✅ Product-launch video rendered for '{owner}/{repo}'.\n"
                f"Video saved to: {video_path}\n"
                "Use add_clip_to_timeline_tool to add this video to the timeline."
            )
        return "❌ Product-launch render returned no video. Check backend logs."

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
        Render a video for a GitHub repository using the full Remotion service (port 4500).
        Fetches repo data, submits a render job, waits for completion, and saves the video.

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
        Render a product-launch video for a GitHub repository using the simpler Remotion service (port 3100).
        Good for quick promotional videos. Fetches repo data, renders, and saves the video.

        Args:
            repo_url: GitHub repository URL (e.g. github.com/owner/repo)
            style: Visual style — "modern", "minimal", "bold" (default: "modern")
            duration: Video duration in seconds (default: 30)
        """
        return render_remotion_product_launch(repo_url, style=style, duration=duration)

    return [
        check_remotion_health_tool,
        render_remotion_from_repo_tool,
        render_remotion_product_launch_tool,
    ]
