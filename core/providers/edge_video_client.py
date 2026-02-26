"""
Edge Video Generation Client — NVIDIA Cosmos on local edge device.

Provides an alternative to Runware for video generation when an edge
device is available on the local network.

Ported from core/src/classes/edge_video_client.py.
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests

from logger import log

# Default edge device URL — override via NVIDIA_EDGE_URL env var
DEFAULT_EDGE_URL = ""


def _get_edge_url() -> str:
    """Get edge device URL from config or env. Returns empty string if not configured."""
    try:
        from config import get_settings
        settings = get_settings()
        url = getattr(settings, "nvidia_edge_url", "") or os.environ.get("NVIDIA_EDGE_URL", "")
        return url.rstrip("/") if url else ""
    except Exception:
        return ""


def is_edge_available(timeout: float = 5.0) -> bool:
    """Check if the edge device is reachable."""
    try:
        url = _get_edge_url()
        if not url:
            return False
        resp = requests.get(f"{url}/health", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def edge_generate_video(
    prompt: str,
    negative_prompt: str = "",
    num_frames: int = 49,
    width: int = 704,
    height: int = 480,
    guidance_scale: float = 7.0,
    seed: int = -1,
    output_path: Optional[str] = None,
    timeout: float = 300.0,
) -> Optional[str]:
    """Generate a video using NVIDIA Cosmos on the edge device.

    Returns the path to the downloaded video file, or None on failure.
    """
    base_url = _get_edge_url()

    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "num_frames": num_frames,
        "width": width,
        "height": height,
        "guidance_scale": guidance_scale,
        "seed": seed,
    }

    try:
        log.info("Edge video generation: %s", prompt[:80])
        resp = requests.post(f"{base_url}/generate", json=payload, timeout=timeout)

        if resp.status_code != 200:
            log.error("Edge generate failed: %d — %s", resp.status_code, resp.text[:200])
            return None

        data = resp.json()
        video_url = data.get("video_url")

        if not video_url:
            log.error("No video_url in edge response")
            return None

        # Download
        if not output_path:
            import tempfile
            fd, output_path = tempfile.mkstemp(suffix=".mp4", prefix="edge_video_")
            os.close(fd)

        dl_resp = requests.get(f"{base_url}{video_url}" if video_url.startswith("/") else video_url, timeout=120)
        if dl_resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(dl_resp.content)
            log.info("Edge video saved: %s (%d bytes)", output_path, len(dl_resp.content))
            return output_path
        else:
            log.error("Edge video download failed: %d", dl_resp.status_code)
            return None

    except requests.Timeout:
        log.error("Edge video generation timed out after %.0fs", timeout)
        return None
    except Exception as e:
        log.error("Edge video generation error: %s", e, exc_info=True)
        return None


def edge_generate_morph_video(
    image1_url: str,
    image2_url: str,
    prompt: str = "smooth morphing transition",
    num_frames: int = 49,
    output_path: Optional[str] = None,
    timeout: float = 300.0,
) -> Optional[str]:
    """Generate a morph transition video between two images using the edge device."""
    base_url = _get_edge_url()

    payload = {
        "image1_url": image1_url,
        "image2_url": image2_url,
        "prompt": prompt,
        "num_frames": num_frames,
    }

    try:
        log.info("Edge morph generation: %s → %s", image1_url[:50], image2_url[:50])
        resp = requests.post(f"{base_url}/morph", json=payload, timeout=timeout)

        if resp.status_code != 200:
            log.error("Edge morph failed: %d — %s", resp.status_code, resp.text[:200])
            return None

        data = resp.json()
        video_url = data.get("video_url")
        if not video_url:
            log.error("No video_url in edge morph response")
            return None

        if not output_path:
            import tempfile
            fd, output_path = tempfile.mkstemp(suffix=".mp4", prefix="edge_morph_")
            os.close(fd)

        dl_resp = requests.get(f"{base_url}{video_url}" if video_url.startswith("/") else video_url, timeout=120)
        if dl_resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(dl_resp.content)
            log.info("Edge morph saved: %s (%d bytes)", output_path, len(dl_resp.content))
            return output_path
        else:
            log.error("Edge morph download failed: %d", dl_resp.status_code)
            return None

    except Exception as e:
        log.error("Edge morph generation error: %s", e, exc_info=True)
        return None
