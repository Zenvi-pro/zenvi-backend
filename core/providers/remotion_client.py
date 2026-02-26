"""
Remotion Rendering Client — for Remotion-based video rendering service.

Two clients:
1. ``RemotionClient`` — full rendering client for the main Remotion service
   (port 4500) supporting Sonar/repo rendering with polling.
2. ``render_product_launch_video()`` — simpler client for local Remotion
   product-launch service (port 3100).

Ported from core/src/classes/video_generation/remotion_client.py and
core/src/classes/remotion_client.py.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests

from logger import log


class RemotionError(Exception):
    """Error from Remotion rendering service."""
    pass


# ---------------------------------------------------------------------------
# Full Remotion Service Client (port 4500)
# ---------------------------------------------------------------------------


class RemotionClient:
    """Client for the Remotion rendering service (``/api/v1``)."""

    def __init__(self, base_url: str = "http://localhost:4500/api/v1"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def health_check(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def render_from_sonar(
        self,
        research_data: Dict[str, Any],
        style: str = "modern",
        duration: int = 30,
        resolution: str = "1080p",
    ) -> Dict[str, Any]:
        """Submit a render job from Sonar research data."""
        payload = {
            "type": "sonar",
            "research_data": research_data,
            "style": style,
            "duration": duration,
            "resolution": resolution,
        }
        resp = self.session.post(f"{self.base_url}/render", json=payload, timeout=30)
        if resp.status_code != 200:
            raise RemotionError(f"Render submission failed: {resp.status_code} — {resp.text[:200]}")
        return resp.json()

    def render_from_repo(
        self,
        repo_url: str,
        repo_data: Dict[str, Any],
        style: str = "modern",
        duration: int = 30,
    ) -> Dict[str, Any]:
        """Submit a render job from a GitHub repo."""
        payload = {
            "type": "repo",
            "repo_url": repo_url,
            "repo_data": repo_data,
            "style": style,
            "duration": duration,
        }
        resp = self.session.post(f"{self.base_url}/render", json=payload, timeout=30)
        if resp.status_code != 200:
            raise RemotionError(f"Render submission failed: {resp.status_code} — {resp.text[:200]}")
        return resp.json()

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Check the status of a render job."""
        resp = self.session.get(f"{self.base_url}/status/{job_id}", timeout=10)
        if resp.status_code != 200:
            raise RemotionError(f"Status check failed: {resp.status_code}")
        return resp.json()

    def download_video(self, job_id: str, output_path: str) -> str:
        """Download a completed render."""
        resp = self.session.get(f"{self.base_url}/download/{job_id}", timeout=120, stream=True)
        if resp.status_code != 200:
            raise RemotionError(f"Download failed: {resp.status_code}")

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        log.info("Remotion video downloaded: %s", output_path)
        return output_path

    def render_and_wait(
        self,
        render_func,
        *args,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
        output_path: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Submit a render, poll until done, download result."""
        result = render_func(*args, **kwargs)
        job_id = result.get("job_id")
        if not job_id:
            raise RemotionError("No job_id in render response")

        return self._poll_for_completion(job_id, poll_interval, max_wait, output_path)

    def _poll_for_completion(
        self,
        job_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 600.0,
        output_path: Optional[str] = None,
    ) -> str:
        start = time.time()
        while time.time() - start < max_wait:
            status = self.get_status(job_id)
            state = status.get("status", "unknown")

            if state == "completed":
                if not output_path:
                    import tempfile
                    fd, output_path = tempfile.mkstemp(suffix=".mp4", prefix="remotion_")
                    os.close(fd)
                return self.download_video(job_id, output_path)

            if state in ("failed", "error"):
                raise RemotionError(f"Render failed: {status.get('error', 'unknown')}")

            log.debug("Remotion job %s: %s (%.0fs)", job_id, state, time.time() - start)
            time.sleep(poll_interval)

        raise RemotionError(f"Render timed out after {max_wait:.0f}s")


# ---------------------------------------------------------------------------
# Simple Product Launch Remotion Client (port 3100)
# ---------------------------------------------------------------------------


def check_remotion_service(base_url: str = "http://localhost:3100") -> bool:
    """Check if the local product-launch Remotion service is running."""
    try:
        resp = requests.get(f"{base_url}/api/health", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def render_product_launch_video(
    repo_data: Dict[str, Any],
    style: str = "modern",
    duration: int = 30,
    base_url: str = "http://localhost:3100",
    output_path: Optional[str] = None,
    timeout: float = 300.0,
) -> Optional[str]:
    """Render a product launch video via the local Remotion service.

    Returns the path to the downloaded video, or None on failure.
    """
    try:
        if not check_remotion_service(base_url):
            log.error("Remotion product-launch service not available at %s", base_url)
            return None

        payload = {
            "repo_data": repo_data,
            "style": style,
            "duration": duration,
        }

        log.info("Rendering product launch video (style=%s, duration=%ds)", style, duration)
        resp = requests.post(f"{base_url}/api/render", json=payload, timeout=timeout)

        if resp.status_code != 200:
            log.error("Product launch render failed: %d — %s", resp.status_code, resp.text[:200])
            return None

        data = resp.json()

        if data.get("status") == "completed" and data.get("video_url"):
            video_url = data["video_url"]
            if not output_path:
                import tempfile
                fd, output_path = tempfile.mkstemp(suffix=".mp4", prefix="product_launch_")
                os.close(fd)

            full_url = f"{base_url}{video_url}" if video_url.startswith("/") else video_url
            dl_resp = requests.get(full_url, timeout=120)
            if dl_resp.status_code == 200:
                with open(output_path, "wb") as f:
                    f.write(dl_resp.content)
                log.info("Product launch video saved: %s", output_path)
                return output_path

        log.error("Unexpected response from product launch render: %s", data)
        return None

    except Exception as e:
        log.error("Product launch render error: %s", e, exc_info=True)
        return None
