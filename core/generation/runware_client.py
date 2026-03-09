"""
Runware API client for video generation (Kling).
Ported from zenvi-core — no Qt, thread-safe.
"""

import base64
import json
import os
import time
import uuid
from logger import log

RUNWARE_API_BASE = "https://api.runware.ai/v1"
POLL_INTERVAL_INITIAL = 2.0
POLL_INTERVAL_MAX = 15.0
POLL_TIMEOUT_SECONDS = 300

# Kling O1 only supports these specific resolutions
_KLING_O1_SUPPORTED_DIMS = [(1920, 1080), (1080, 1920), (1440, 1440)]


def _snap_to_kling_resolution(w, h, model=""):
    """Snap arbitrary width/height to the closest supported Kling O1 resolution.

    Only applies when the model string contains 'kling' and the requested
    dimensions are not already in the supported set.  For non-Kling models
    the original values are returned unchanged.

    Supported resolutions: 1920x1080, 1080x1920, 1440x1440.
    """
    if "kling" not in (model or "").lower():
        return w, h
    if w is None or h is None:
        return 1920, 1080  # default landscape
    if (int(w), int(h)) in _KLING_O1_SUPPORTED_DIMS:
        return int(w), int(h)
    aspect = w / max(h, 1)
    if aspect > 1.2:
        return 1920, 1080   # landscape
    elif aspect < 0.8:
        return 1080, 1920   # portrait
    else:
        return 1440, 1440   # square-ish


# Kling O1 only allows these specific durations
_KLING_O1_ALLOWED_DURATIONS = [5, 10]


def _snap_to_kling_duration(duration, model=""):
    """Snap duration to nearest allowed value for Kling O1 (5 or 10 seconds)."""
    if "kling" not in (model or "").lower():
        return int(duration)
    # Pick the nearest allowed value
    best = min(_KLING_O1_ALLOWED_DURATIONS, key=lambda d: abs(d - duration))
    return int(best)


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
    duration_seconds=5,
    model="klingai:kling@o1",
    width=1920,
    height=1080,
    input_video_url=None,
    input_image_path=None,
):
    """
    Generate video via Runware. Prefers the official SDK (WebSocket); falls back to REST.
    
    Args:
        api_key: Runware API key
        prompt: Text prompt describing the video
        duration_seconds: Duration of the video (1-10 seconds)
        model: Kling model identifier (default: klingai:kling@o1)
        width: Output width
        height: Output height
        input_video_url: Optional URL of an input video for video-to-video generation.
                         If provided, the model should support it (e.g. Kling O1 video-edit).
        input_image_path: Optional local path to a frame image for image-to-video (i2v).
                          Used as the first frame reference for Kling.
    Returns:
        (video_url, None) on success, or (None, error_message) on failure.
    """
    if not api_key or not str(api_key).strip():
        return None, "Video generation is not configured. Add your Runware API key in Preferences."
    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return None, "Prompt must be at least 2 characters."
    api_key = api_key.strip()
    duration_int = _snap_to_kling_duration(max(1, min(10, duration_seconds)), model)

    # Snap to model-supported resolution (Kling O1 only allows specific dims)
    width, height = _snap_to_kling_resolution(width, height, model)
    log.info("runware_generate_video: model=%s resolution=%dx%d duration=%r (type=%s)",
             model, width, height, duration_int, type(duration_int).__name__)

    # Try SDK first
    try:
        from runware import Runware, IVideoInference, IFrameImage
        from runware.types import IAsyncTaskResponse, IVideoInputs
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rw = None
        try:
            rw = Runware(api_key=api_key, timeout=POLL_TIMEOUT_SECONDS)
            loop.run_until_complete(rw.connect())
            
            # Construct request
            req_kwargs = dict(
                positivePrompt=prompt,
                model=model,
                deliveryMethod="async",
            )
            # Kling O1 video-edit: duration is inferred from input video
            if not input_video_url:
                req_kwargs["duration"] = duration_int
            if width is not None:
                req_kwargs["width"] = int(width)
            if height is not None:
                req_kwargs["height"] = int(height)
            req = IVideoInference(**req_kwargs)
            # Force duration to int – the SDK declares it as Optional[float]
            # but the Kling O1 API rejects floats like 5.0
            if req.duration is not None:
                req.duration = int(req.duration)
            
            # Image-to-video (i2v): use a local frame image as starting reference
            # NOTE: The Runware SDK 0.5.0 has a bug where _processVideoImages()
            # stores the base64 result in frame_item.inputImages (dynamic attr),
            # but _addVideoImages() serialises via asdict() which only includes
            # declared dataclass fields (inputImage, frame).  So we convert to a
            # base64 data-URI *ourselves* before passing it to IFrameImage.
            if input_image_path and os.path.isfile(input_image_path):
                log.info("Using frame image for i2v: %s", input_image_path)
                import mimetypes as _mt
                _mime, _ = _mt.guess_type(input_image_path)
                if not _mime:
                    _mime = "image/png"
                with open(input_image_path, "rb") as _fh:
                    _raw = _fh.read()
                _b64 = base64.b64encode(_raw).decode("utf-8")
                _data_uri = f"data:{_mime};base64,{_b64}"
                log.info("i2v: converted %d bytes → data-URI (%d chars), mode=image-to-video",
                         len(_raw), len(_data_uri))
                req.frameImages = [IFrameImage(inputImage=_data_uri)]
            # Video-to-video: use input video URL
            elif input_video_url:
                req.inputs = IVideoInputs(video=input_video_url)
            
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
        "model": model, "outputFormat": "MP4", "deliveryMethod": "async",
    }
    if not input_video_url and not input_image_path:
        task["duration"] = int(duration_int)
    if width is not None:
        task["width"] = int(width)
    if height is not None:
        task["height"] = int(height)
    if input_image_path and os.path.isfile(input_image_path):
        # i2v: pass the frame image as base64 frameImage
        with open(input_image_path, "rb") as img_f:
            img_b64 = base64.b64encode(img_f.read()).decode("ascii")
        task["frameImages"] = [{"inputImage": f"data:image/png;base64,{img_b64}"}]
    elif input_video_url:
        task["inputs"] = {"video": input_video_url}
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
    """
    Download video from URL to local path, or copy if it's already a local file.
    
    Returns:
        (True, None) on success, (False, error_message) on failure.
    """
    if not video_url or not local_path:
        return False, "Missing URL or path."

    # Handle local file paths
    import os
    if os.path.isfile(video_url):
        try:
            import shutil
            shutil.copy2(video_url, local_path)
            return True, None
        except OSError as e:
            return False, f"Failed to copy local video: {e}"

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
    except requests.RequestException as e:
        log.error("Download failed: %s", e)
        return False, f"Download failed: {e}."
    except OSError as e:
        log.error("Write failed: %s", e)
        return False, f"Could not write file: {e}."


def runware_generate_morph_video(
    api_key,
    prompt,
    start_image_url,
    end_image_url,
    duration_seconds=5,
    model="klingai:kling@o1",
    width=1920,
    height=1080,
):
    """
    Generate a morph/transition video using Kling with start and end frame images.
    The model generates a video that smoothly transitions from start_image to end_image.

    Args:
        api_key: Runware API key
        prompt: Text prompt describing the transition
        start_image_url: Public URL of the first frame (start of transition)
        end_image_url: Public URL of the last frame (end of transition)
        duration_seconds: Duration of the generated video (float, 1-10)
        model: Kling model identifier
        width: Output width (None to let model decide)
        height: Output height (None to let model decide)

    Returns:
        (video_url, None) on success, or (None, error_message) on failure.
    """
    if not api_key or not str(api_key).strip():
        return None, "Runware API key not configured."
    if not start_image_url or not end_image_url:
        return None, "Both start and end image URLs are required for morph transition."
    prompt = (prompt or "").strip()
    if len(prompt) < 2:
        return None, "Prompt must be at least 2 characters."

    api_key = api_key.strip()
    duration_val = _snap_to_kling_duration(max(1, min(10, duration_seconds)), model)

    try:
        from runware import Runware, IVideoInference
        from runware.types import IAsyncTaskResponse, IVideoInputs, IInputFrame
        import asyncio

        # Snap to supported resolution
        res_w, res_h = _snap_to_kling_resolution(width, height, model)
        log.info("Morph transition: model=%s duration=%d resolution=%dx%d start=%s end=%s",
                 model, duration_val, res_w, res_h, start_image_url[:60], end_image_url[:60])

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        rw = None
        try:
            rw = Runware(api_key=api_key, timeout=POLL_TIMEOUT_SECONDS)
            loop.run_until_complete(rw.connect())

            # Kling O1 requires frame images via inputs.frameImages (not top-level)
            inputs_obj = IVideoInputs(
                frameImages=[
                    IInputFrame(image=start_image_url, frame="first"),
                    IInputFrame(image=end_image_url, frame="last"),
                ],
            )

            req_kwargs = dict(
                positivePrompt=prompt,
                model=model,
                width=res_w,
                height=res_h,
                duration=duration_val,
                deliveryMethod="async",
                inputs=inputs_obj,
            )

            req = IVideoInference(**req_kwargs)
            # Force duration to int – Kling O1 API rejects floats
            if req.duration is not None:
                req.duration = int(req.duration)
            result = loop.run_until_complete(rw.videoInference(requestVideo=req))

            task_uuid = None
            if isinstance(result, IAsyncTaskResponse):
                task_uuid = getattr(result, "taskUUID", None) or getattr(result, "task_uuid", None)
            if not task_uuid:
                return None, "Runware SDK did not return a task UUID for morph."

            videos = loop.run_until_complete(rw.getResponse(task_uuid, numberResults=1))
            if videos and len(videos) > 0 and getattr(videos[0], "videoURL", None):
                url = videos[0].videoURL
                log.info("Morph transition video generated: %s", url[:80] if url else None)
                return url, None
            return None, "Runware SDK returned no video URL for morph."
        finally:
            if rw is not None:
                try:
                    loop.run_until_complete(rw.disconnect())
                except Exception:
                    pass
            loop.close()
    except ImportError:
        return None, "Runware SDK is required for morph transitions. Install with: pip install runware"
    except Exception as e:
        log.error("Morph transition failed: %s", e, exc_info=True)
        return None, f"Morph transition failed: {e}."
