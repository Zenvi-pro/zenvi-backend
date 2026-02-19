"""
Tag management endpoints.
"""

from fastapi import APIRouter
from api.schemas import TagsUpdateRequest, TagSearchRequest, StatusResponse

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
def list_all_tags():
    """List all tags across all files."""
    from core.managers.tags import get_tag_manager
    return get_tag_manager().get_all_tags()


@router.get("/{file_id}")
def get_tags(file_id: str):
    """Get tags for a specific file."""
    from core.managers.tags import get_tag_manager
    return get_tag_manager().get_tags(file_id)


@router.post("")
def update_tags(req: TagsUpdateRequest):
    """Add or update tags for a file."""
    from core.managers.tags import get_tag_manager
    get_tag_manager().add_tags(req.file_id, req.tags)
    return StatusResponse(success=True, message="Tags updated")


@router.delete("/{file_id}")
def remove_tags(file_id: str):
    """Remove all tags for a file."""
    from core.managers.tags import get_tag_manager
    get_tag_manager().remove_tags(file_id)
    return StatusResponse(success=True, message="Tags removed")


@router.post("/search")
def search_by_tag(req: TagSearchRequest):
    """Search for files by tag value."""
    from core.managers.tags import get_tag_manager
    file_ids = get_tag_manager().search_by_tag(req.tag_value, req.tag_type)
    return {"file_ids": file_ids}


@router.get("/statistics/summary")
def tag_statistics():
    """Get tag statistics."""
    from core.managers.tags import get_tag_manager
    return get_tag_manager().get_statistics()


@router.post("/analyze")
async def analyze_video_tags(req: dict):
    """AI-powered video tagging/analysis (replaces GeminiVideoTagger on frontend)."""
    from datetime import datetime
    video_path = req.get("video_path", "")
    if not video_path:
        return _empty_ai_metadata()

    # Try OpenAI vision analysis
    try:
        from config import get_settings
        from core.providers.openai_provider import OpenAIProvider
        settings = get_settings()
        api_key = settings.openai_api_key
        if api_key:
            provider = OpenAIProvider(api_key=api_key)
            if provider.is_available():
                import asyncio
                result = await provider.analyze_image(video_path)
                tags = result.to_dict()
                # Store tags in tag manager
                from core.managers.tags import get_tag_manager
                import os
                file_id = os.path.basename(video_path)
                get_tag_manager().add_tags(file_id, tags)
                return {
                    "analyzed": True,
                    "analysis_version": "2.0",
                    "analysis_date": datetime.now().isoformat(),
                    "provider": "openai",
                    "scene_descriptions": [],
                    "tags": {
                        "objects": tags.get("objects", []),
                        "scenes": tags.get("scenes", []),
                        "activities": tags.get("activities", []),
                        "mood": tags.get("mood", []),
                        "quality": tags.get("quality_scores", {}),
                    },
                    "faces": tags.get("faces", []),
                    "colors": tags.get("colors", {}),
                    "audio_analysis": {},
                    "description": tags.get("description", ""),
                    "confidence": tags.get("confidence", 0.0),
                }
    except Exception as e:
        from logger import log
        log.error("Video tagging failed: %s", e)

    return _empty_ai_metadata()


def _empty_ai_metadata():
    """Return default empty ai_metadata dict."""
    from datetime import datetime
    return {
        "analyzed": False,
        "analysis_version": "2.0",
        "analysis_date": datetime.now().isoformat(),
        "provider": "backend",
        "scene_descriptions": [],
        "tags": {"objects": [], "scenes": [], "activities": [], "mood": [], "quality": {}},
        "faces": [],
        "colors": {},
        "audio_analysis": {},
        "description": "",
        "confidence": 0.0,
    }
