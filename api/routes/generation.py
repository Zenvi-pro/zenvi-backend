"""Video generation endpoints (Kling via Runware)."""

from fastapi import APIRouter
from api.schemas import (
    GenerateVideoRequest, GenerateMorphVideoRequest, GenerateVideoResponse,
)
from logger import log

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/video", response_model=GenerateVideoResponse)
def generate_video(req: GenerateVideoRequest):
    """Generate a video from a text prompt (text-to-video or video-to-video)."""
    from core.generation.runware_client import runware_generate_video, download_video_to_path
    from config import get_settings
    import tempfile
    import os

    settings = get_settings()
    api_key = settings.runware_api_key
    if not api_key:
        return GenerateVideoResponse(error="Runware API key not configured")

    url, err = runware_generate_video(
        api_key=api_key,
        prompt=req.prompt,
        duration_seconds=req.duration_seconds,
        model=req.model,
        width=req.width,
        height=req.height,
        input_video_url=req.input_video_url,
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


@router.post("/morph", response_model=GenerateVideoResponse)
def generate_morph_video(req: GenerateMorphVideoRequest):
    """Generate a morph/transition video between two frames using Kling."""
    from core.generation.runware_client import runware_generate_morph_video, download_video_to_path
    from config import get_settings
    import tempfile
    import os

    settings = get_settings()
    api_key = settings.runware_api_key
    if not api_key:
        return GenerateVideoResponse(error="Runware API key not configured")

    url, err = runware_generate_morph_video(
        api_key=api_key,
        prompt=req.prompt,
        start_image_url=req.start_image_url,
        end_image_url=req.end_image_url,
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
