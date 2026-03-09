"""Video generation endpoints (Kling via Runware)."""

import base64
import json
import os
import subprocess
import tempfile

from fastapi import APIRouter
from api.schemas import (
    GenerateVideoRequest, GenerateMorphVideoRequest, GenerateVideoResponse,
)
from logger import log

router = APIRouter(prefix="/generation", tags=["generation"])

# Kling O1 video-edit requires input video dimensions ∈ [720, 2160].
_KLING_MIN_DIM = 720
_KLING_MAX_DIM = 2160


def _ensure_seed_video_min_resolution(seed_path: str) -> str:
    """Re-encode the seed video if its dimensions fall outside [720, 2160].

    Returns the (possibly new) path to the conforming seed video.
    """
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", seed_path],
            capture_output=True, text=True, timeout=15,
        )
        info = json.loads(probe.stdout)
        vid_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
        if not vid_stream:
            return seed_path
        w = int(vid_stream.get("width", 0))
        h = int(vid_stream.get("height", 0))
    except Exception as exc:
        log.warning("_ensure_seed_video_min_resolution: ffprobe failed: %s", exc)
        return seed_path

    needs_resize = w < _KLING_MIN_DIM or h < _KLING_MIN_DIM or w > _KLING_MAX_DIM or h > _KLING_MAX_DIM
    if not needs_resize:
        return seed_path

    # Compute new dimensions inside [720, 2160], preserving aspect ratio.
    new_w, new_h = w, h
    if new_w < _KLING_MIN_DIM or new_h < _KLING_MIN_DIM:
        scale_up = max(_KLING_MIN_DIM / max(new_w, 1), _KLING_MIN_DIM / max(new_h, 1))
        new_w = int(new_w * scale_up)
        new_h = int(new_h * scale_up)
    if new_w > _KLING_MAX_DIM or new_h > _KLING_MAX_DIM:
        scale_dn = min(_KLING_MAX_DIM / max(new_w, 1), _KLING_MAX_DIM / max(new_h, 1))
        new_w = int(new_w * scale_dn)
        new_h = int(new_h * scale_dn)
    # libx264 needs even dims
    new_w += new_w % 2
    new_h += new_h % 2

    log.info("Resizing seed video %dx%d → %dx%d to meet Kling O1 [720,2160] range", w, h, new_w, new_h)
    out_dir = tempfile.mkdtemp(prefix="zenvi_seed_resize_")
    out_path = os.path.join(out_dir, "seed_resized.mp4")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", seed_path,
                "-vf", f"scale={new_w}:{new_h}:force_original_aspect_ratio=decrease,"
                       f"pad={new_w}:{new_h}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an",
                out_path,
            ],
            capture_output=True, timeout=60, check=True,
        )
        return out_path
    except Exception as exc:
        log.warning("_ensure_seed_video_min_resolution: ffmpeg resize failed: %s", exc)
        return seed_path


@router.post("/video", response_model=GenerateVideoResponse)
def generate_video(req: GenerateVideoRequest):
    """Generate a video from a text prompt (text-to-video or video-to-video)."""
    from core.generation.runware_client import runware_generate_video, download_video_to_path
    from config import get_settings
    import tempfile

    settings = get_settings()
    api_key = settings.runware_api_key
    if not api_key:
        return GenerateVideoResponse(error="Runware API key not configured")

    # Convert local paths to data URIs for Runware API.
    # Kling O1 video-edit requires input video dims ∈ [720, 2160].
    # If the seed video is too small, re-encode it with ffmpeg first.
    seed_video_uri = None
    if req.seed_video_path and os.path.isfile(req.seed_video_path):
        _seed_path = _ensure_seed_video_min_resolution(req.seed_video_path)
        with open(_seed_path, "rb") as f:
            raw = f.read()
        seed_video_uri = f"data:video/mp4;base64,{base64.b64encode(raw).decode('ascii')}"
        log.info("Converted seed video %s to data URI (%d bytes)", _seed_path, len(raw))

    frame_images_uris = None
    if req.frame_images_paths:
        frame_images_uris = []
        for fi in req.frame_images_paths:
            fpath = fi.get("path", "")
            frame_label = fi.get("frame", "first")
            if fpath and os.path.isfile(fpath):
                with open(fpath, "rb") as f:
                    raw = f.read()
                data_uri = f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}"
                frame_images_uris.append({"inputImage": data_uri, "frame": frame_label})

    url, err = runware_generate_video(
        api_key=api_key,
        prompt=req.prompt,
        duration_seconds=req.duration_seconds,
        model=req.model,
        width=req.width,
        height=req.height,
        input_video_url=req.input_video_url,
        input_image_path=req.input_image_path,
        seed_video=seed_video_uri,
        strength=req.strength,
        frame_images=frame_images_uris,
    )

    if err:
        return GenerateVideoResponse(error=err)

    # Download to temp file
    output_dir = tempfile.mkdtemp(prefix="zenvi_gen_")
    output_path = os.path.join(output_dir, "generated_video.mp4")
    ok, dl_err = download_video_to_path(url, output_path)

    if not ok:
        return GenerateVideoResponse(video_url=url, error=dl_err)

    return GenerateVideoResponse(video_url=url, local_path=output_path)


def _morph_resolve_image(path: str | None) -> str:
    """Convert a local image path to a base64 data URI for the morph endpoint."""
    if not path:
        return ""
    if not os.path.isfile(path):
        log.warning("Morph image path not found: %s", path)
        return ""
    with open(path, "rb") as f:
        raw = f.read()
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}.get(ext, "jpeg")
    data_uri = f"data:image/{mime};base64,{base64.b64encode(raw).decode('ascii')}"
    log.info("Converted morph image %s to data URI (%d bytes)", path, len(raw))
    return data_uri


@router.post("/morph", response_model=GenerateVideoResponse)
def generate_morph_video(req: GenerateMorphVideoRequest):
    """Generate a morph/transition video between two frames using Kling."""
    from core.generation.runware_client import runware_generate_morph_video, download_video_to_path
    from config import get_settings
    import tempfile

    settings = get_settings()
    api_key = settings.runware_api_key
    if not api_key:
        return GenerateVideoResponse(error="Runware API key not configured")

    url, err = runware_generate_morph_video(
        api_key=api_key,
        prompt=req.prompt,
        start_image_url=req.start_image_url or _morph_resolve_image(req.start_image_path),
        end_image_url=req.end_image_url or _morph_resolve_image(req.end_image_path),
        duration_seconds=req.duration_seconds,
        model=req.model,
        width=req.width,
        height=req.height,
    )

    if err:
        return GenerateVideoResponse(error=err)

    output_dir = tempfile.mkdtemp(prefix="zenvi_morph_")
    output_path = os.path.join(output_dir, "morph_video.mp4")
    ok, dl_err = download_video_to_path(url, output_path)

    if not ok:
        return GenerateVideoResponse(video_url=url, error=dl_err)

    return GenerateVideoResponse(video_url=url, local_path=output_path)
