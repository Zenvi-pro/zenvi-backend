"""
Video generation endpoints.
"""

from fastapi import APIRouter
from api.schemas import GenerateVideoRequest, GenerateVideoResponse
from logger import log

router = APIRouter(prefix="/generation", tags=["generation"])


@router.post("/video", response_model=GenerateVideoResponse)
def generate_video(req: GenerateVideoRequest):
    """Generate a video from a text prompt."""
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
        negative_prompt=req.negative_prompt,
        fps=req.fps,
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
