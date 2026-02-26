"""
Morph Transition Pipeline.

Extracts frames from two clips, uploads them, generates a morph video
via Runware (or edge fallback), and returns the path.

Ported from core/src/classes/ai_morph_transition.py.
All Qt dependencies removed — frame extraction uses ffmpeg directly.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Optional

from logger import log


def _extract_frame(video_path: str, timestamp: float, output_path: str) -> bool:
    """Extract a single frame from a video using ffmpeg."""
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-ss", str(timestamp),
                "-i", video_path,
                "-frames:v", "1",
                "-q:v", "2",
                output_path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0 and os.path.isfile(output_path)
    except Exception as e:
        log.error("Frame extraction failed: %s", e)
        return False


def _upload_to_temp_hosting(image_path: str) -> Optional[str]:
    """Upload an image to temporary hosting and return URL.

    Uses free public file hosting as a convenience fallback.
    For production, configure a private storage service (S3, GCS, etc.).
    """
    import requests

    # Try 0x0.st (simple file host)
    try:
        with open(image_path, "rb") as f:
            resp = requests.post("https://0x0.st", files={"file": f}, timeout=30)
        if resp.status_code == 200:
            url = resp.text.strip()
            if url.startswith("http"):
                log.info("Uploaded to 0x0.st: %s", url)
                return url
    except Exception as e:
        log.debug("0x0.st upload failed: %s", e)

    # Try file.io
    try:
        with open(image_path, "rb") as f:
            resp = requests.post("https://file.io", files={"file": f}, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            url = data.get("link")
            if url:
                log.info("Uploaded to file.io: %s", url)
                return url
    except Exception as e:
        log.debug("file.io upload failed: %s", e)

    log.error("All temp hosting uploads failed for %s", image_path)
    return None


def generate_morph_transition(
    clip1_path: str,
    clip2_path: str,
    clip1_end_time: float,
    clip2_start_time: float = 0.0,
    duration_seconds: float = 2.0,
    output_path: Optional[str] = None,
    use_edge: bool = False,
) -> Optional[str]:
    """Generate a morph transition video between two clips.

    Pipeline:
    1. Extract the last frame from clip1 and first frame from clip2
    2. Upload frames to temp hosting
    3. Generate morph video via Runware (or edge device)
    4. Download and return path

    Returns the path to the generated morph video, or None on failure.
    """
    work_dir = tempfile.mkdtemp(prefix="zenvi_morph_")

    try:
        # Step 1: Extract frames
        frame1_path = os.path.join(work_dir, "frame1.jpg")
        frame2_path = os.path.join(work_dir, "frame2.jpg")

        if not _extract_frame(clip1_path, clip1_end_time, frame1_path):
            log.error("Failed to extract frame from clip1")
            return None

        if not _extract_frame(clip2_path, clip2_start_time, frame2_path):
            log.error("Failed to extract frame from clip2")
            return None

        log.info("Extracted frames for morph transition")

        if use_edge:
            return _generate_via_edge(frame1_path, frame2_path, output_path, work_dir)

        # Step 2: Upload to temp hosting (needed for Runware API)
        url1 = _upload_to_temp_hosting(frame1_path)
        url2 = _upload_to_temp_hosting(frame2_path)

        if not url1 or not url2:
            log.error("Failed to upload frames to temp hosting")
            return None

        # Step 3: Generate via Runware
        try:
            from core.generation.runware_client import runware_generate_morph_video, download_video_to_path
            from config import get_settings

            settings = get_settings()
            api_key = settings.runware_api_key
            if not api_key:
                log.error("Runware API key not configured")
                return None

            morph_result = runware_generate_morph_video(
                api_key=api_key,
                image_url_1=url1,
                image_url_2=url2,
            )

            if not morph_result:
                log.error("Runware morph generation returned no result")
                return None

            video_url = morph_result if isinstance(morph_result, str) else morph_result.get("video_url", "")

            if not video_url:
                log.error("No video URL in morph result")
                return None

            if not output_path:
                output_path = os.path.join(work_dir, "morph_transition.mp4")

            download_video_to_path(video_url, output_path)
            log.info("Morph transition generated: %s", output_path)
            return output_path

        except ImportError as e:
            log.error("Runware client not available: %s", e)
            return None

    except Exception as e:
        log.error("Morph transition generation failed: %s", e, exc_info=True)
        return None


def _generate_via_edge(
    frame1_path: str,
    frame2_path: str,
    output_path: Optional[str],
    work_dir: str,
) -> Optional[str]:
    """Generate morph via NVIDIA edge device."""
    try:
        from core.providers.edge_video_client import edge_generate_morph_video

        url1 = _upload_to_temp_hosting(frame1_path)
        url2 = _upload_to_temp_hosting(frame2_path)
        if not url1 or not url2:
            return None

        if not output_path:
            output_path = os.path.join(work_dir, "morph_transition.mp4")

        result = edge_generate_morph_video(url1, url2, output_path=output_path)
        return result

    except ImportError:
        log.error("Edge video client not available")
        return None
    except Exception as e:
        log.error("Edge morph generation failed: %s", e, exc_info=True)
        return None
