"""
Media analysis endpoints.
"""

from typing import Dict, List, Any
from fastapi import APIRouter, BackgroundTasks
from api.schemas import StatusResponse
from logger import log

router = APIRouter(prefix="/media", tags=["media"])

# In-memory analysis queue
_analysis_queue: List[Dict[str, Any]] = []
_analysis_state = {"processing": False, "current_file": ""}


@router.post("/command")
async def process_media_command(command: str):
    """Process a natural-language media management command."""
    from core.media.manager import get_ai_media_manager
    manager = get_ai_media_manager()
    result = await manager.process_command(command)
    return result


@router.get("/statistics")
async def get_statistics():
    """Get all media statistics (tags, faces, collections)."""
    from core.media.manager import get_ai_media_manager
    manager = get_ai_media_manager()
    result = await manager._get_statistics()
    return result


@router.get("/analysis/status")
def get_analysis_status():
    """Get the analysis queue status."""
    pending = [item for item in _analysis_queue if item.get("status") == "pending"]
    processing = [item for item in _analysis_queue if item.get("status") == "processing"]
    return {
        "pending": len(pending),
        "processing": len(processing),
        "total": len(_analysis_queue),
        "current_file": _analysis_state.get("current_file", ""),
        "queue": _analysis_queue,
    }


@router.post("/analysis/start")
async def start_analysis(background_tasks: BackgroundTasks):
    """Start processing the analysis queue."""
    if _analysis_state["processing"]:
        return StatusResponse(success=True, message="Analysis already running")

    pending = [item for item in _analysis_queue if item.get("status") == "pending"]
    if not pending:
        return StatusResponse(success=True, message="No files to analyze")

    def _process_queue():
        _analysis_state["processing"] = True
        try:
            for item in _analysis_queue:
                if item.get("status") != "pending":
                    continue
                item["status"] = "processing"
                _analysis_state["current_file"] = item.get("file_path", "")
                try:
                    # Run AI analysis via OpenAI provider
                    from config import get_settings
                    from core.providers.openai_provider import OpenAIProvider
                    import asyncio
                    settings = get_settings()
                    api_key = settings.openai_api_key
                    if api_key:
                        provider = OpenAIProvider(api_key=api_key)
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(provider.analyze_image(item["file_path"]))
                        loop.close()
                        tags = result.to_dict()
                        from core.managers.tags import get_tag_manager
                        get_tag_manager().add_tags(item["file_id"], tags)
                    item["status"] = "completed"
                except Exception as e:
                    log.error("Analysis failed for %s: %s", item.get("file_path"), e)
                    item["status"] = "failed"
                    item["error"] = str(e)
        finally:
            _analysis_state["processing"] = False
            _analysis_state["current_file"] = ""

    background_tasks.add_task(_process_queue)
    return StatusResponse(success=True, message=f"Analysis started for {len(pending)} files")


@router.post("/analysis/clear")
def clear_analysis_queue():
    """Clear the analysis queue."""
    _analysis_queue.clear()
    _analysis_state["processing"] = False
    _analysis_state["current_file"] = ""
    return StatusResponse(success=True, message="Analysis queue cleared")


@router.post("/analysis/queue")
def queue_file_for_analysis(req: dict):
    """Add a file to the analysis queue."""
    file_id = req.get("file_id", "")
    file_path = req.get("file_path", "")
    media_type = req.get("media_type", "video")

    if not file_id or not file_path:
        return StatusResponse(success=False, message="file_id and file_path are required")

    # Check for duplicates
    for item in _analysis_queue:
        if item.get("file_id") == file_id:
            return StatusResponse(success=True, message="File already in queue")

    _analysis_queue.append({
        "file_id": file_id,
        "file_path": file_path,
        "media_type": media_type,
        "status": "pending",
    })
    return StatusResponse(success=True, message="File queued for analysis")
