"""
Pexels stock-video search and download endpoints.
"""

import os
import re
import tempfile
import urllib.request
from pathlib import Path

import requests as _requests
from fastapi import APIRouter, Query

from api.schemas import (
    PexelsDownloadRequest,
    PexelsDownloadResponse,
    PexelsSearchResponse,
    PexelsVideo,
    PexelsVideoFile,
)
from config import get_settings

router = APIRouter(prefix="/pexels", tags=["pexels"])

_PEXELS_API_BASE = "https://api.pexels.com/videos"


def _get_api_key() -> str:
    return get_settings().pexels_api_key


def _pexels_headers() -> dict:
    return {"Authorization": _get_api_key()}


@router.get("/search", response_model=PexelsSearchResponse)
def pexels_search(
    query: str = Query(..., description="Search query"),
    per_page: int = Query(15, ge=1, le=80),
    page: int = Query(1, ge=1),
):
    """Search Pexels for stock videos matching *query*."""
    api_key = _get_api_key()
    if not api_key:
        return PexelsSearchResponse(error="PEXELS_API_KEY is not configured")

    try:
        resp = _requests.get(
            f"{_PEXELS_API_BASE}/search",
            headers=_pexels_headers(),
            params={"query": query, "per_page": per_page, "page": page},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return PexelsSearchResponse(error=str(exc))

    videos = []
    for v in data.get("videos", []):
        files = [
            PexelsVideoFile(
                id=f.get("id", 0),
                quality=f.get("quality") or "",
                file_type=f.get("file_type") or "",
                width=f.get("width"),
                height=f.get("height"),
                fps=f.get("fps"),
                link=f.get("link") or "",
            )
            for f in v.get("video_files", [])
            if (f.get("file_type") or "").startswith("video/")
        ]
        user = v.get("user") or {}
        videos.append(
            PexelsVideo(
                id=v.get("id", 0),
                width=v.get("width", 0),
                height=v.get("height", 0),
                duration=v.get("duration", 0),
                image=v.get("image", ""),
                url=v.get("url", ""),
                video_files=files,
                video_pictures=v.get("video_pictures", []),
                user_name=user.get("name", ""),
            )
        )

    return PexelsSearchResponse(
        videos=videos,
        total_results=data.get("total_results", 0),
        page=data.get("page", page),
        per_page=data.get("per_page", per_page),
    )


@router.post("/download", response_model=PexelsDownloadResponse)
def pexels_download(req: PexelsDownloadRequest):
    """Download a Pexels video to the local temp directory.

    The ``link`` field should be a direct MP4 URL from ``video_files[n].link``.
    Returns the absolute path to the downloaded file.
    """
    api_key = _get_api_key()
    if not api_key:
        return PexelsDownloadResponse(error="PEXELS_API_KEY is not configured")

    # Build a safe filename
    safe_name = re.sub(r"[^\w\-]", "_", req.filename) if req.filename else f"pexels_{req.video_id}"
    dest_dir = Path(tempfile.gettempdir()) / "zenvi_pexels"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{safe_name}.mp4"

    # Return cached file if already downloaded
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return PexelsDownloadResponse(local_path=str(dest_path))

    # Try direct download first (Pexels links are direct MP4 URLs)
    try:
        resp = _requests.get(
            req.link,
            headers={**_pexels_headers(), "User-Agent": "Mozilla/5.0"},
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()
        with open(dest_path, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 64):
                if chunk:
                    fh.write(chunk)
        if dest_path.stat().st_size > 0:
            return PexelsDownloadResponse(local_path=str(dest_path))
    except Exception as exc:
        # Fall through to yt-dlp
        pass

    # Fallback: yt-dlp (handles Vimeo CDN redirects)
    try:
        import subprocess
        result = subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "-o", str(dest_path),
                "--merge-output-format", "mp4",
                req.link,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0 and dest_path.exists() and dest_path.stat().st_size > 0:
            return PexelsDownloadResponse(local_path=str(dest_path))
        return PexelsDownloadResponse(error=result.stderr or "yt-dlp failed")
    except FileNotFoundError:
        return PexelsDownloadResponse(error="Download failed and yt-dlp is not installed")
    except Exception as exc:
        return PexelsDownloadResponse(error=str(exc))
