"""
TwelveLabs indexing endpoints.
"""

from fastapi import APIRouter, BackgroundTasks
from api.schemas import IndexRequest, IndexResultSchema, StatusResponse

router = APIRouter(prefix="/indexing", tags=["indexing"])


@router.get("/status")
def indexing_status():
    """Check if TwelveLabs indexing is configured."""
    from core.indexing.twelvelabs import is_configured
    return {"configured": is_configured()}


@router.post("", response_model=IndexResultSchema)
def index_video(req: IndexRequest):
    """Index a video file (blocking — for background use /indexing/async)."""
    from core.indexing.twelvelabs import index_video_blocking

    result = index_video_blocking(
        file_path=req.file_path,
        index_name=req.index_name,
        filename=req.filename,
        existing_index_id=req.existing_index_id,
    )
    return IndexResultSchema(**{k: v for k, v in result.items() if k in IndexResultSchema.model_fields})


@router.post("/async", response_model=StatusResponse)
def index_video_async(req: IndexRequest, background_tasks: BackgroundTasks):
    """Index a video file in the background."""
    from core.indexing.twelvelabs import index_video_blocking

    def _index():
        index_video_blocking(
            file_path=req.file_path,
            index_name=req.index_name,
            filename=req.filename,
            existing_index_id=req.existing_index_id,
        )

    background_tasks.add_task(_index)
    return StatusResponse(success=True, message="Indexing started in background")


@router.post("/index", response_model=IndexResultSchema)
def index_video_at_path(req: IndexRequest):
    """Index a video file (alias endpoint for frontend compatibility)."""
    from core.indexing.twelvelabs import index_video_blocking

    result = index_video_blocking(
        file_path=req.file_path,
        index_name=req.index_name,
        filename=req.filename,
        existing_index_id=req.existing_index_id,
    )
    return IndexResultSchema(**{k: v for k, v in result.items() if k in IndexResultSchema.model_fields})


@router.delete("/video", response_model=StatusResponse)
def delete_indexed_video(index_id: str, video_id: str):
    """Delete a video from the search index."""
    from core.indexing.twelvelabs import delete_video_from_index

    ok = delete_video_from_index(index_id=index_id, video_id=video_id)
    return StatusResponse(success=ok, message="Deleted" if ok else "Failed to delete")
