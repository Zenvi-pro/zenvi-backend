"""
Shared helper utilities for OpenShot tools.

These helpers are used by both server-side and frontend-delegated tools.
Functions that need the Qt app are NOT included here; they live on the frontend
in tool_handlers.py.
"""

import base64
import os
import subprocess

from logger import log


def fmt_mmss(seconds: float) -> str:
    """Format seconds as M:SS."""
    try:
        seconds = float(seconds)
    except Exception:
        seconds = 0.0
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def ffmpeg_run(args: list[str]) -> tuple[bool, str]:
    """Run an ffmpeg command and return (success, error_message)."""
    try:
        p = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        if p.returncode != 0:
            return False, (p.stderr or p.stdout or "ffmpeg failed")
        return True, ""
    except FileNotFoundError:
        return False, "ffmpeg not found. Install ffmpeg to enable AI video processing."
    except Exception as e:
        return False, str(e)


def file_to_data_uri(path: str, media_type: str) -> tuple[str | None, str | None]:
    """Read a file and return a data: URI, or (None, error)."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        if len(raw) > 50 * 1024 * 1024:
            return None, "Seed media is too large to send as base64."
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{media_type};base64,{b64}", None
    except OSError as e:
        return None, f"Failed to read media: {e}"


def ffprobe_has_audio(path: str) -> bool:
    """Return True if the media file has at least one audio stream."""
    try:
        p = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index", "-of", "csv=p=0", path,
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        )
        return bool((p.stdout or "").strip())
    except Exception:
        return False


def is_extreme_for_4_seconds(prompt: str) -> tuple[bool, str]:
    """Heuristic guardrail — return (is_too_extreme, reason)."""
    text = (prompt or "").strip().lower()
    if len(text) < 2:
        return True, "Prompt is too short."

    multi_markers = [
        "then ", "after that", "afterwards", "meanwhile", "next ",
        "cut to", "scene change", "montage", "several", "multiple",
        "a series of", "over the course of", "gradually",
        "time-lapse", "timelapse",
    ]
    if sum(1 for m in multi_markers if m in text) >= 2:
        return True, "Request describes multiple steps/scenes; keep it to one simple action for a 4s insert."

    extreme_markers = [
        "explode", "nuke", "earthquake", "tsunami", "apocalypse",
        "destroy the city", "teleport", "time travel", "turn into",
        "transform into", "grow wings", "summon", "giant",
        "entire crowd", "army", "hundreds of", "thousands of",
    ]
    if any(m in text for m in extreme_markers):
        return True, "Request is too large/extreme to fit plausibly into a 4s insert."

    if len(text) > 240:
        return True, "Prompt is too detailed for a 4s insert; simplify to the single key change."

    return False, ""
