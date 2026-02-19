"""
Runware API client for video generation (Vidu).
Ported from zenvi-core verbatim — no Qt, thread-safe.
"""

import base64
import json
import time
import uuid
from logger import log

RUNWARE_API_BASE = "https://api.runware.ai/v1"
POLL_INTERVAL_INITIAL = 2.0
POLL_INTERVAL_MAX = 15.0
POLL_TIMEOUT_SECONDS = 300


def _model_supports_fps(model: str) -> bool:
    m = (model or "").strip().lower()
    if m.startswith("vidu:2@"):
        return False
    return True


def _model_supports_seed_video(model: str) -> bool:
    m = (model or "").strip().lower()
    if m.startswith("vidu:2@"):
        return False
    return True


def _try_parse_runware_error(body_text: str) -> dict:
    try:
        return json.loads(body_text) if body_text else {}
    except Exception:
        return {}


def _as_data_uri(media_type: str, raw_bytes: bytes) -> str:
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:{media_type};base64,{b64}"


def _poll_runware_task_rest(api_key: str, task_uuid: str, *, timeout_seconds: float = POLL_TIMEOUT_SECONDS):
    try:
        import requests
    except ImportError:
        return None, "requests library is required."

    headers = {"Content-Type": "application/json"}
    start = time.time()
    interval = float(POLL_INTERVAL_INITIAL)
    last_status = "processing"
    while True:
        if time.time() - start > float(timeout_seconds or POLL_TIMEOUT_SECONDS):
            return None, f"Video generation timed out (last status: {last_status})."
        payload = [
            {"taskType": "authentication", "apiKey": api_key},
            {"taskType": "getResponse", "taskUUID": str(task_uuid)},
        ]
        try:
            r = requests.post(RUNWARE_API_BASE, headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            data = r.json() if r.content else {}
        except Exception as e:
            return None, f"Runware polling failed: {e}."
        errors = data.get("errors") or []
        if errors:
            msg = errors[0].get("message", str(errors[0])) if isinstance(errors[0], dict) else str(errors[0])
            return None, f"Runware error: {msg}."
        items = data.get("data") or []
        item = None
        for it in items:
            if isinstance(it, dict) and str(it.get("taskUUID")) == str(task_uuid):
                item = it
                break
        if not item and items:
            item = items[0] if isinstance(items[0], dict) else None
        if item:
            last_status = item.get("status", last_status)
            if str(last_status).lower() == "success":
                url = item.get("videoURL")
                if url:
                    return url, None
                return None, "Runware returned success but no videoURL."
            if str(last_status).lower() in ("error", "failed", "canceled", "cancelled"):
                return None, "Runware task failed."
        time.sleep(interval)
        interval = min(float(POLL_INTERVAL_MAX), interval * 1.4)


def runware_generate_video(
    api_key,
    prompt,
    duration_seconds=4,
    model="vidu:3@2",
    width=640,
    height=352,
    *,
    negative_prompt=None,
    fps=24,
    seed_video=None,
    strength=None,
    frame_images=None,
    reference_videos=None,
):
    """Generate video via Runware. Returns (video_url, None) or (None, error_message)."""
    if not api_key or not str(api_key).strip():
        return None, "Video generation is not configured. Add your Runware API key."
    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return None, "Prompt must be at least 2 characters."
    api_key = api_key.strip()
    duration_int = int(max(1, min(10, duration_seconds)))
    if not _model_supports_seed_video(model):
        seed_video = None
        strength = None

    # Try SDK first
    try:
        from runware import Runware, IVideoInference
        from runware.types import IAsyncTaskResponse
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rw = None
        try:
            rw = Runware(api_key=api_key, timeout=POLL_TIMEOUT_SECONDS)
            loop.run_until_complete(rw.connect())
            req_kwargs = {
                "positivePrompt": prompt, "model": model, "duration": duration_int,
                "width": int(width), "height": int(height), "deliveryMethod": "async",
            }
            if negative_prompt:
                req_kwargs["negativePrompt"] = str(negative_prompt)
            if fps is not None and _model_supports_fps(model):
                req_kwargs["fps"] = int(fps)
            if seed_video:
                req_kwargs["seedVideo"] = seed_video
            if strength is not None:
                req_kwargs["strength"] = float(strength)
            if frame_images:
                req_kwargs["frameImages"] = frame_images
            if reference_videos:
                req_kwargs["referenceVideos"] = reference_videos
            req = IVideoInference(**req_kwargs)
            result = loop.run_until_complete(rw.videoInference(requestVideo=req))
            task_uuid = getattr(result, "taskUUID", None) or getattr(result, "task_uuid", None)
            if not task_uuid:
                return None, "Runware SDK did not return a task UUID."
            poll_start = time.time()
            interval = float(POLL_INTERVAL_INITIAL)
            while time.time() - poll_start < float(POLL_TIMEOUT_SECONDS):
                videos = loop.run_until_complete(rw.getResponse(task_uuid, numberResults=1))
                if videos and len(videos) > 0 and getattr(videos[0], "videoURL", None):
                    return videos[0].videoURL, None
                time.sleep(interval)
                interval = min(float(POLL_INTERVAL_MAX), interval * 1.4)
            return None, "Runware SDK polling timed out."
        finally:
            if rw is not None:
                try:
                    loop.run_until_complete(rw.disconnect())
                except Exception:
                    pass
            loop.close()
    except ImportError:
        pass
    except Exception as e:
        log.error("Runware SDK failed: %s", e, exc_info=True)

    # REST fallback
    try:
        import requests
    except ImportError:
        return None, "requests library is required."
    task_uuid = str(uuid.uuid4())
    headers = {"Content-Type": "application/json"}
    task = {
        "taskType": "videoInference", "taskUUID": task_uuid, "positivePrompt": prompt,
        "model": model, "duration": float(duration_int), "width": int(width),
        "height": int(height), "deliveryMethod": "async", "outputFormat": "MP4", "outputQuality": 95,
    }
    if fps is not None and _model_supports_fps(model):
        task["fps"] = int(fps)
    if negative_prompt:
        task["negativePrompt"] = str(negative_prompt)
    if seed_video:
        task["seedVideo"] = seed_video
    if strength is not None:
        task["strength"] = float(strength)
    if frame_images:
        task["frameImages"] = frame_images
    if reference_videos:
        task["referenceVideos"] = reference_videos
    payload = [{"taskType": "authentication", "apiKey": api_key}, task]
    try:
        r = requests.post(RUNWARE_API_BASE, headers=headers, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return None, f"Runware API request failed: {e}"
    errors = data.get("errors") or []
    if errors:
        return None, f"Runware error: {errors[0].get('message', str(errors[0]))}."
    return _poll_runware_task_rest(api_key, task_uuid)


def download_video_to_path(video_url, local_path):
    if not video_url or not local_path:
        return False, "Missing URL or path."
    try:
        import requests
    except ImportError:
        return False, "requests library is required."
    try:
        r = requests.get(video_url, timeout=120, stream=True)
        r.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        return True, None
    except Exception as e:
        log.error("Download failed: %s", e)
        return False, f"Download failed: {e}."
