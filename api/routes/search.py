"""
Search endpoints.
"""

from fastapi import APIRouter
from api.schemas import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_clips(req: SearchRequest):
    """Search for clips matching a query."""
    from core.indexing.twelvelabs import search_index

    top_k = req.page_limit if req.page_limit and req.page_limit > req.top_k else req.top_k
    results = search_index(
        req.query,
        index_id=req.index_id or "",
        top_k=top_k,
        video_id=req.video_id or "",
    )
    # search_index may return a dict with an "error" key on failure
    if isinstance(results, dict) and "error" in results:
        return SearchResponse(results=[], query=req.query, error=results["error"])
    if not isinstance(results, list):
        results = []
    return SearchResponse(
        results=[SearchResultItem(**r) for r in results],
        query=req.query,
    )
