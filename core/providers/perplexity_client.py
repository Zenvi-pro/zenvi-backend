"""
Perplexity Sonar API client for research.
Logic-only, no Qt. Thread-safe.
"""

from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from logger import log

DEFAULT_BASE_URL = "https://api.perplexity.ai/"
DEFAULT_MODEL = "sonar-pro"


@dataclass(frozen=True)
class PerplexityError(Exception):
    message: str
    status_code: Optional[int] = None
    detail: Optional[str] = None

    def __str__(self) -> str:
        bits = [self.message]
        if self.status_code is not None:
            bits.append(f"(status={self.status_code})")
        if self.detail:
            bits.append(self.detail)
        return " ".join(bits)


def _norm_base_url(base_url: str) -> str:
    base = (base_url or "").strip() or DEFAULT_BASE_URL
    if not base.endswith("/"):
        base += "/"
    return base


def _auth_headers(api_key: str) -> Dict[str, str]:
    key = (api_key or "").strip()
    if not key:
        raise PerplexityError("Missing Perplexity API key.")
    return {"Authorization": f"Bearer {key}"}


def _parse_json_response(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        text = getattr(resp, "text", "") or ""
        raise PerplexityError(
            "Failed to parse JSON response.",
            status_code=getattr(resp, "status_code", None),
            detail=text[:500]
        )


def _raise_for_status(resp) -> None:
    if 200 <= int(resp.status_code) < 300:
        return
    status = int(resp.status_code)
    detail = None
    try:
        data = _parse_json_response(resp)
        if isinstance(data, dict):
            if "error" in data:
                err = data["error"]
                detail = err.get("message") if isinstance(err, dict) else str(err)
            elif "detail" in data:
                detail = str(data.get("detail") or "")
    except Exception:
        pass
    if not detail:
        detail = (getattr(resp, "text", "") or "")[:500]
    msgs = {
        401: "Authentication failed. Check your Perplexity API key.",
        403: "Access denied. API key may lack permissions.",
        429: "Rate limit exceeded. Please wait.",
        400: f"Bad request: {detail}",
    }
    raise PerplexityError(msgs.get(status, "Perplexity API request failed."), status_code=status, detail=detail)


def perplexity_search(
    *,
    api_key: str,
    query: str,
    model: str = DEFAULT_MODEL,
    return_images: bool = True,
    return_related_questions: bool = True,
    search_domain_filter: Optional[List[str]] = None,
    search_recency_filter: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 60.0,
) -> Dict[str, Any]:
    """Search using Perplexity Sonar API. Returns {content, citations, images, related_questions}."""
    if not (query or "").strip():
        raise PerplexityError("Query is required for search.")

    import requests

    messages = [{"role": "user", "content": str(query).strip()}]
    payload: Dict[str, Any] = {
        "model": str(model).strip() or DEFAULT_MODEL,
        "messages": messages,
    }
    if return_images:
        payload["return_images"] = True
    if return_related_questions:
        payload["return_related_questions"] = True
    if search_domain_filter:
        domains = [d.strip() for d in search_domain_filter if (d or "").strip()]
        if domains:
            payload["search_domain_filter"] = domains
    if (search_recency_filter or "").strip():
        recency = str(search_recency_filter).strip().lower()
        if recency in ("month", "week", "day"):
            payload["search_recency_filter"] = recency

    url = _norm_base_url(base_url) + "chat/completions"
    headers = _auth_headers(api_key)
    headers["Content-Type"] = "application/json"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise PerplexityError(f"Perplexity API request failed: {exc}") from exc

    _raise_for_status(resp)
    data = _parse_json_response(resp)

    if not isinstance(data, dict):
        raise PerplexityError("Unexpected response format.", status_code=int(resp.status_code))

    content = ""
    choices = data.get("choices", [])
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message", {})
        if isinstance(message, dict):
            content = message.get("content", "")

    citations = data.get("citations", [])
    if not isinstance(citations, list):
        citations = []

    images = data.get("images", [])
    if not isinstance(images, list):
        images = []

    related_questions = data.get("related_questions", [])
    if not isinstance(related_questions, list):
        related_questions = []

    return {
        "content": str(content).strip(),
        "citations": [str(c).strip() for c in citations if (c or "").strip()],
        "images": [
            {"url": str(img.get("url", "")).strip(), "description": str(img.get("description", "")).strip()}
            for img in images
            if isinstance(img, dict) and (img.get("url") or "").strip()
        ],
        "related_questions": [str(q).strip() for q in related_questions if (q or "").strip()],
    }


def download_image(*, image_url: str, dest_path: str, timeout_seconds: float = 60.0) -> Tuple[bool, Optional[str]]:
    """Download an image from URL to dest_path. Returns (success, error_or_none)."""
    url = (image_url or "").strip()
    path = (dest_path or "").strip()
    if not url or not path:
        return False, "Missing image_url or dest_path."
    import requests
    try:
        r = requests.get(url, timeout=float(timeout_seconds), stream=True)
        r.raise_for_status()
        dest_dir = os.path.dirname(path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return True, None
    except requests.RequestException as exc:
        log.error("Image download failed: %s", exc)
        return False, f"Download failed: {exc}."
    except OSError as exc:
        log.error("Image write failed: %s", exc)
        return False, f"Could not write file: {exc}."


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^\w\-\.]", "_", name)
    return safe[:50] if len(safe) > 50 else (safe or "image")


def research_and_download_images(
    *,
    api_key: str,
    query: str,
    max_images: int = 5,
    dest_dir: str,
    model: str = DEFAULT_MODEL,
    search_domain_filter: Optional[List[str]] = None,
    search_recency_filter: str = "",
    base_url: str = DEFAULT_BASE_URL,
    timeout_seconds: float = 120.0,
) -> Dict[str, Any]:
    """Search + download top N images. Returns {summary, citations, image_paths, ...}."""
    result = perplexity_search(
        api_key=api_key, query=query, model=model,
        return_images=True, return_related_questions=True,
        search_domain_filter=search_domain_filter,
        search_recency_filter=search_recency_filter,
        base_url=base_url,
        timeout_seconds=float(timeout_seconds) / 2,
    )
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)

    images = result.get("images", [])
    max_imgs = max(0, int(max_images))
    downloaded_images = []
    failed_images = []
    image_timeout = min(30.0, float(timeout_seconds) / max(1, max_imgs) / 2)

    for i, img in enumerate(images[:max_imgs]):
        img_url = img.get("url", "")
        if not img_url:
            continue
        filename_base = _sanitize_filename(os.path.basename(img_url.split("?")[0]))
        if not filename_base or filename_base == "image":
            filename_base = f"image_{i + 1}"
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{filename_base}_{unique_id}.jpg"
        dest_path = os.path.join(dest_dir, filename)
        ok, err = download_image(image_url=img_url, dest_path=dest_path, timeout_seconds=image_timeout)
        if ok:
            downloaded_images.append({"path": dest_path, "url": img_url, "description": img.get("description", "")})
        else:
            failed_images.append({"url": img_url, "error": err or "Unknown error"})
            log.warning("Failed to download image %s: %s", img_url, err)

    return {
        "summary": result.get("content", ""),
        "citations": result.get("citations", []),
        "image_paths": [img["path"] for img in downloaded_images],
        "downloaded_images": downloaded_images,
        "failed_images": failed_images,
        "related_questions": result.get("related_questions", []),
    }
